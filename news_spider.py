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
    # ----- 国内核心 -----
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📰 财联社": "/cls/hot",
    "⏱️ 金十数据": "/jin10/important",
    "📈 华尔街见闻": "/wallstreetcn/hot",
    "💬 雪球热门": "/xueqiu/hot",
    # ----- 国际源 -----
    "📈 Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "💹 FT Markets": "https://www.ft.com/markets?format=rss",
    "📊 The Economist": "https://www.economist.com/finance-and-economics/rss.xml",
    "🏛️ 美联储": "https://www.federalreserve.gov/feeds/allpress.xml",
}

# 权重配置
URGENT_KEYWORDS = ["紧急", "突发", "重磅", "快讯", "最新", "刚刚", "央行", "证监会", "BREAKING", "URGENT", "FED"]
POLICY_KEYWORDS = ["降息", "加息", "降准", "利率", "CPI", "GDP", "RATE", "HIKE", "CUT"]
MARKET_KEYWORDS = ["A股", "港股", "美股", "股票", "证券", "股市", "STOCKS", "MARKET"]
NEGATIVE_KEYWORDS = ["广告", "推广", "福利", "课程", "保险"]

KEYWORD_WEIGHTS = {
    **dict.fromkeys(URGENT_KEYWORDS, 25),
    **dict.fromkeys(POLICY_KEYWORDS, 20),
    **dict.fromkeys(MARKET_KEYWORDS, 15),
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ========== 2. 翻译引擎 (Google 免 Key 版) ==========
def translate_to_chinese(text):
    """简单有效的自动翻译函数"""
    # 如果本身包含中文字符，直接返回
    if re.search(r'[\u4e00-\u9fa5]', text):
        return text
    
    try:
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": "en",
            "tl": "zh-CN",
            "dt": "t",
            "q": text
        }
        resp = requests.get(url, params=params, timeout=10)
        # 返回结构类似 [[[译文, 原文, ...]]]
        result = resp.json()
        translated_text = "".join([sentence[0] for sentence in result[0]])
        return f"{translated_text} (原文: {text})"
    except Exception as e:
        logging.warning(f"翻译失败: {e}")
        return text

# ========== 3. 核心功能 ==========

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
        # 保持缓存干净，只留3天
        now = datetime.now()
        self.cache['news'] = {k: v for k, v in self.cache['news'].items() 
                             if (now - datetime.fromisoformat(v)).days < 3}
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
            
            # 执行评分 (基于原文)
            score = 0
            for keyword, weight in KEYWORD_WEIGHTS.items():
                if keyword.upper() in raw_title.upper(): score += weight
            
            if score > 0:
                # 📢 关键：执行自动翻译
                final_title = translate_to_chinese(raw_title)
                news_pool.append({
                    "title": final_title,
                    "link": entry.get('link', ''),
                    "source": name,
                    "score": score
                })
        logging.info(f"✅ {name} 扫描完成")

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
        f"# 💰 全球股市情报 (已翻译)\n\n"
        f"| 项目 | 状态 |\n| :--- | :--- |\n| 📦 捕获总量 | {len(sorted_news)} |\n| ⏰ 刷新时间 | {bj_time} |\n\n"
        f"### 🚩 【重磅关注】\n" + ("\n".join(hot_items) if hot_items else "> 暂无重磅") + "\n\n"
        f"### 📢 【核心快讯】\n" + ("\n".join(reg_items) if reg_items else "> 监测中") + "\n\n"
        f"---\n💡 *已自动识别英文并实时翻译成中文*"
    )

    requests.post(f"https://sctapi.ftqq.com/{send_key}.send", data={"title": f"全球快报|{bj_time[:10]}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
