import feedparser
import requests
import os
import json
import logging
import random
import re
import urllib3
from datetime import datetime, timedelta
from pathlib import Path

# 禁用 SSL 警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 1. 配置区 ==========
RSSHUB_NODES = [
    "https://rss-hub-nu-one.vercel.app",
    "https://rsshub.app",
    "https://rsshub.icu"
]

FEEDS = {
    # 国内核心
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📰 财联社": "/cls/hot",
    "⏱️ 金十数据": "/jin10/important",
    "📈 华尔街见闻": "/wallstreetcn/hot",
    "📡 证券时报": "/stcn/news",
    # 国际源
    "📈 Bloomberg": "https://feeds.bloomberg.com/markets/news.rss",
    "💹 FT Markets": "https://www.ft.com/markets?format=rss",
    "🏛️ 美联储": "https://www.federalreserve.gov/feeds/allpress.xml",
}

# 权重词 (中英双语支持)
URGENT = ["紧急", "突发", "重磅", "刚刚", "BREAKING", "URGENT", "FED", "央行"]
POLICY = ["降息", "加息", "降准", "利率", "LPR", "CPI", "RATE", "HIKE", "CUT"]
MARKET = ["A股", "港股", "美股", "股市", "指数", "STOCKS", "MARKET"]

KEYWORD_WEIGHTS = {**dict.fromkeys(URGENT, 25), **dict.fromkeys(POLICY, 20), **dict.fromkeys(MARKET, 15)}
NEGATIVE_KEYWORDS = ["广告", "推广", "福利", "课程"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ========== 2. 自动翻译引擎 ==========
def translate_to_chinese(text):
    """自动识别英文并翻译"""
    if re.search(r'[\u4e00-\u9fa5]', text): # 如果包含中文则不翻译
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t", "q": text}
        resp = requests.get(url, params=params, timeout=10)
        result = resp.json()
        translated = "".join([s[0] for s in result[0]])
        return f"{translated} (原文: {text})"
    except:
        return text

# ========== 3. 核心逻辑 ==========
class NewsCache:
    def __init__(self, cache_file='news_cache.json'):
        self.cache_file = Path(cache_file)
        self.cache = self.load_cache()

    def load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {'news': {}}
        return {'news': {}}

    def is_duplicate(self, title):
        key = title[:25]
        if key in self.cache['news']: return True
        self.cache['news'][key] = datetime.now().isoformat()
        return False

    def save_cache(self):
        now = datetime.now()
        self.cache['news'] = {k: v for k, v in self.cache['news'].items() if (now - datetime.fromisoformat(v)).days < 3}
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

def fetch_news():
    news_pool = []
    cache = NewsCache()
    headers = {'User-Agent': 'Mozilla/5.0'}

    for name, path in FEEDS.items():
        feed = None
        urls = [path] if path.startswith('http') else [f"{node}{path}" for node in RSSHUB_NODES]
        if not path.startswith('http'): random.shuffle(urls)

        for url in urls:
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    if feed.entries: break
            except: continue

        if not feed or not feed.entries: continue

        for entry in feed.entries:
            raw_title = entry.get('title', '').strip()
            if not raw_title or any(k in raw_title.upper() for k in NEGATIVE_KEYWORDS) or cache.is_duplicate(raw_title):
                continue
            
            score = 0
            for keyword, weight in KEYWORD_WEIGHTS.items():
                if keyword.upper() in raw_title.upper(): score += weight
            
            if score > 0:
                final_title = translate_to_chinese(raw_title)
                news_pool.append({"title": final_title, "link": entry.get('link', ''), "source": name, "score": score})
    
    cache.save_cache()
    return sorted(news_pool, key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, reg_items = [], []

    for item in sorted_news[:25]:
        source_line = f"- *(来源：{item['source']} | [原文]({item['link']}))*"
        formatted = f"## {item['title']}\n{source_line}\n"
        if item['score'] >= 25: hot_items.append(f"🚩 {formatted}")
        else: reg_items.append(f"🔹 {formatted}")

    desp = (
        f"# 💰 全球股市情报 (已自动翻译)\n\n"
        f"| 项目 | 实时状态 |\n| :--- | :--- |\n| 📦 今日新增 | {len(sorted_news)} 条 |\n| ⏰ 刷新时间 | {bj_time} |\n\n"
        f"### 🚩 【今日重磅】\n" + ("\n".join(hot_items) if hot_items else "> 暂无重磅资讯") + "\n\n"
        f"### 📢 【核心快讯】\n" + ("\n".join(reg_items) if reg_items else "> 正在监测中...") + "\n\n"
        f"---\n💡 *提示：系统已自动识别并翻译 Bloomberg/FT 等国际信源*"
    )

    requests.post(f"https://sctapi.ftqq.com/{send_key}.send", data={"title": f"股市快报|{bj_time[:10]}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
