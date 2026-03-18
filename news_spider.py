import feedparser
import requests
import os
import json
import logging
import random
from datetime import datetime, timedelta
from pathlib import Path

# ========== 1. 配置区 ==========
# 定义多个 RSSHub 节点轮询，防止单一节点挂掉
RSSHUB_NODES = [
    "https://rss-hub-nu-one.vercel.app",
    "https://rsshub.app",
    "https://rsshub.icu"
]

FEEDS = {
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📈 经观股市": "/eeo/category/11",
    "💰 21世纪经济": "/21jingji/channel/investment"
}

# 权重配置 (保留你定义的逻辑)
URGENT_KEYWORDS = ["紧急", "突发", "重磅", "快讯", "最新", "刚刚", "央行", "证监会"]
POLICY_KEYWORDS = ["降息", "加息", "降准", "利率", "CPI", "GDP", "经济数据"]
MARKET_KEYWORDS = ["A股", "港股", "美股", "股票", "证券", "股市", "大盘", "指数"]
COMPANY_KEYWORDS = ["腾讯", "阿里", "美团", "茅台", "英伟达", "特斯拉", "华为", "小米"]
EARNINGS_KEYWORDS = ["财报", "业绩", "营收", "净利润", "同比增长"]
RISK_KEYWORDS = ["暴跌", "暴涨", "崩盘", "熔断", "退市", "利空", "立案", "处罚"]

KEYWORD_WEIGHTS = {
    **dict.fromkeys(URGENT_KEYWORDS, 25),
    **dict.fromkeys(POLICY_KEYWORDS, 20),
    **dict.fromkeys(MARKET_KEYWORDS, 15),
    **dict.fromkeys(COMPANY_KEYWORDS, 15),
    **dict.fromkeys(EARNINGS_KEYWORDS, 12),
    **dict.fromkeys(RISK_KEYWORDS, 10),
}

NEGATIVE_KEYWORDS = ["广告", "推广", "福利", "领奖", "课程", "保险", "八卦", "综艺"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ========== 2. 核心类与函数 ==========

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
        key = title[:20] # 用前20个字符去重
        if key in self.cache['news']: return True
        self.cache['news'][key] = datetime.now().isoformat()
        return False

    def save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False)

def calculate_score(title):
    score = 0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in title: score += weight
    return score

def fetch_news():
    news_pool = []
    cache = NewsCache()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    
    for name, path in FEEDS.items():
        feed = None
        random.shuffle(RSSHUB_NODES) # 随机打乱节点顺序
        for node in RSSHUB_NODES:
            try:
                resp = requests.get(f"{node}{path}", headers=headers, timeout=15)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    if feed.entries: break
            except: continue

        if not feed or not feed.entries: continue

        for entry in feed.entries:
            title = entry.title.strip()
            if any(k in title for k in NEGATIVE_KEYWORDS): continue
            if cache.is_duplicate(title): continue
            
            score = calculate_score(title)
            if score > 0:
                news_pool.append({"title": title, "link": entry.link, "source": name, "score": score})
    
    cache.save_cache()
    return sorted(news_pool, key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, reg_items = [], []
    
    for item in sorted_news[:22]:
        # 视觉精修：##标题大，来源行小号斜体
        source_line = f"- *(来源：{item['source']} | [原文]({item['link']}))*"
        formatted = f"## {item['title']}\n{source_line}\n"
        if item['score'] >= 25: hot_items.append(f"🚩 {formatted}")
        else: reg_items.append(f"🔹 {formatted}")

    hot_str = "\n".join(hot_items) if hot_items else "> 暂无超高热度资讯"
    reg_str = "\n".join(reg_items) if reg_items else "> 暂无核心快讯"
    
    desp = (
        f"# 💰 股市情报快报\n\n"
        f"| 项目 | 数据 |\n| :--- | :--- |\n| 📦 聚合总数 | {len(sorted_news)} |\n| ⏰ 刷新时间 | {bj_time} |\n\n"
        f"### 🚩 【重磅关注】\n{hot_str}\n\n"
        f"### 📢 【市场快讯】\n{reg_str}\n\n"
        f"---\n💡 *已启用智能去重与关键词分级系统*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市快报|{bj_time[:10]}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
