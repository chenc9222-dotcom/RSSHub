import feedparser
import requests
import os
import json
import logging
import random
import urllib3
from datetime import datetime, timedelta
from pathlib import Path

# 禁用不安全请求警告（针对某些机构官网的 SSL 证书问题）
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========== 1. 配置区 ==========
RSSHUB_NODES = [
    "https://rss-hub-nu-one.vercel.app",
    "https://rsshub.app",
    "https://rsshub.icu"
]

FEEDS = {
    # ----- 国内核心（基于 RSSHub）-----
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📈 经观股市": "/eeo/category/11",
    "💰 21世纪经济": "/21jingji/channel/investment",
    "📰 财联社·热门": "/cls/hot",
    "⏱️ 金十数据": "/jin10/important",
    "📈 华尔街见闻": "/wallstreetcn/hot",
    "📡 证券时报": "/stcn/news",
    "💬 雪球热门": "/xueqiu/hot",

    # ----- 全球视野（直接 URL）-----
    "📈 Bloomberg Markets": "https://feeds.bloomberg.com/markets/news.rss",
    "💹 FT Markets": "https://www.ft.com/markets?format=rss",
    "📊 The Economist": "https://www.economist.com/finance-and-economics/rss.xml",
    "📉 Seeking Alpha": "https://seekingalpha.com/tag/editors-picks.xml",
    "🚀 TechCrunch": "https://techcrunch.com/feed/",
    "🏦 Yahoo Finance": "https://finance.yahoo.com/news/rssindex",

    # ----- 官方机构（直接 URL）-----
    "🏛️ 美联储": "https://www.federalreserve.gov/feeds/allpress.xml",
    "🇨🇳 央行发布": "http://www.pbc.gov.cn/rmyh/105729/113540/common_rss.shtml",
    "📈 统计局": "http://www.stats.gov.cn/tjsj/zxfb/_rss.xml",
}

# 权重配置 (加入英文关键词支持)
URGENT_KEYWORDS = ["紧急", "突发", "重磅", "快讯", "最新", "刚刚", "央行", "证监会", "Breaking", "Urgent", "FED"]
POLICY_KEYWORDS = ["降息", "加息", "降准", "利率", "CPI", "GDP", "Economic", "Rate", "Hike", "Cut"]
MARKET_KEYWORDS = ["A股", "港股", "美股", "股票", "证券", "股市", "指数", "Stocks", "Market"]
COMPANY_KEYWORDS = ["腾讯", "阿里", "美团", "茅台", "英伟达", "特斯拉", "Nvidia", "Tesla", "Apple"]
RISK_KEYWORDS = ["暴跌", "暴涨", "崩盘", "退市", "利空", "调查", "Plunge", "Surge", "Risk"]

KEYWORD_WEIGHTS = {
    **dict.fromkeys(URGENT_KEYWORDS, 25),
    **dict.fromkeys(POLICY_KEYWORDS, 20),
    **dict.fromkeys(MARKET_KEYWORDS, 15),
    **dict.fromkeys(COMPANY_KEYWORDS, 15),
    **dict.fromkeys(RISK_KEYWORDS, 10),
}

NEGATIVE_KEYWORDS = ["广告", "推广", "福利", "课程", "保险", "综艺", "八卦"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ========== 2. 核心逻辑 ==========

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
        key = title[:25]  # 取前25字去重
        if key in self.cache['news']: return True
        self.cache['news'][key] = datetime.now().isoformat()
        return False

    def save_cache(self):
        # 仅保留最近 3 天的记录，防止文件无限增大
        now = datetime.now()
        filtered_news = {
            k: v for k, v in self.cache['news'].items()
            if (now - datetime.fromisoformat(v)).days < 3
        }
        self.cache['news'] = filtered_news
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

def calculate_score(title):
    score = 0
    # 转换为大写以匹配英文关键词
    upper_title = title.upper()
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword.upper() in upper_title: score += weight
    return score

def fetch_news():
    news_pool = []
    cache = NewsCache()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}

    for name, path in FEEDS.items():
        feed = None
        # 判断是直接 URL 还是 RSSHub 路径
        if path.startswith('http'):
            urls = [path]
        else:
            random.shuffle(RSSHUB_NODES)
            urls = [f"{node}{path}" for node in RSSHUB_NODES]

        for url in urls:
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    if feed.entries: break
            except: continue

        if not feed or not feed.entries:
            logging.info(f"⚪ {name}: 暂无内容")
            continue

        count = 0
        for entry in feed.entries:
            title = entry.get('title', '').strip()
            if not title or any(k in title for k in NEGATIVE_KEYWORDS) or cache.is_duplicate(title):
                continue
            
            score = calculate_score(title)
            if score > 0:
                news_pool.append({
                    "title": title,
                    "link": entry.get('link', ''),
                    "source": name,
                    "score": score
                })
                count += 1
        logging.info(f"✅ {name}: 成功获取 {count} 条")

    cache.save_cache()
    return sorted(news_pool, key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key:
        logging.error("❌ 环境变量 FEISHU_WEBHOOK 未设置")
        return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, reg_items = [], []

    # 选取精华前 25 条
    for item in sorted_news[:25]:
        # 视觉效果：标题加粗变大，来源行小号斜体
        source_line = f"- *(来源：{item['source']} | [查看原文]({item['link']}))*"
        formatted = f"## {item['title']}\n{source_line}\n"
        
        if item['score'] >= 25: hot_items.append(f"🚩 {formatted}")
        else: reg_items.append(f"🔹 {formatted}")

    hot_str = "\n".join(hot_items) if hot_items else "> 暂无超高权重资讯"
    reg_str = "\n".join(reg_items) if reg_items else "> 监测中..."

    desp = (
        f"# 💰 全球股市情报速递\n\n"
        f"| 项目 | 实时汇总 |\n| :--- | :--- |\n| 📦 今日捕获 | {len(sorted_news)} 条 |\n| ⏰ 刷新时间 | {bj_time} |\n\n"
        f"### 🚩 【重磅关注】\n{hot_str}\n\n"
        f"### 📢 【核心快讯】\n{reg_str}\n\n"
        f"---\n💡 *已整合 Bloomberg/FT 等全球信源，启用智能去重系统*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        requests.post(url, data={"title": f"股市快报|{bj_time[:10]}", "desp": desp}, timeout=10)
        logging.info("🚀 飞书推送任务完成")
    except Exception as e:
        logging.error(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
