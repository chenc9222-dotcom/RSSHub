import feedparser
import requests
import os
import random
from datetime import datetime, timedelta

# --- 1. 容错配置区 ---
# 定义多个镜像地址，自动轮询防止单个节点失效
RSSHUB_NODES = [
    "https://rsshub.app",
    "https://rsshub.icu",
    "https://rsshub.rssbuddy.com"
]

FEEDS_PATH = {
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📈 东方财富": "/eastmoney/report/strategy",
    "💰 21世纪经济": "/21jingji/channel/investment",
    "🌐 华尔街见闻": "/wallstreetcn/news/global"
}

# 降低门槛：只要含有这些词，就给分展示
BASE_KEYWORDS = ["股", "市", "金", "财", "债", "经", "行", "汇"]
CORE_KEYWORDS = ["重磅", "紧急", "政策", "降息", "加息", "突破", "暴涨", "暴跌"]

def fetch_news():
    news_pool = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    
    # 随机选择一个初始节点
    base_url = random.choice(RSSHUB_NODES)
    print(f"🚀 正在通过节点 {base_url} 抓取...")

    for name, path in FEEDS_PATH.items():
        try:
            full_url = f"{base_url}{path}"
            resp = requests.get(full_url, headers=headers, timeout=25)
            feed = feedparser.parse(resp.text)
            
            if not feed.entries:
                # 如果这个源没抓到，尝试换个节点抓这个源
                alt_url = random.choice([n for n in RSSHUB_NODES if n != base_url])
                resp = requests.get(f"{alt_url}{path}", headers=headers, timeout=20)
                feed = feedparser.parse(resp.text)

            for entry in feed.entries:
                title = entry.title.strip()
                # 统计基础分：只要标题里有金融相关字眼就给 10 分保底
                score = 0
                if any(k in title for k in BASE_KEYWORDS): score += 10
                if any(k in title for k in CORE_KEYWORDS): score += 20
                
                # 只要有分数（哪怕只有10分）就展示，彻底降低门槛
                if score >= 10:
                    news_pool.append({"title": title, "link": entry.link, "source": name, "score": score})
        except:
            continue

    # 去重
    unique_news = {}
    for item in news_pool:
        t = item['title']
        if t not in unique_news or item['score'] > unique_news[t]['score']:
            unique_news[t] = item
            
    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, regular_items = [], []
    
    # 只要有 25 分就是热点，其余全是快讯
    for item in sorted_news[:25]:
        # 视觉精修：##标题巨大，来源行极其微小
        source_line = f"- *(来源：{item['source']} | [原文]({item['link']}))*"
        content = f"## {item['title']}\n{source_line}\n"
        
        if item['score'] >= 25:
            hot_items.append(f"🚩 {content}")
        else:
            regular_items.append(f"🔹 {content}")

    # 预拼接避免反斜杠报错
    hot_str = "\n".join(hot_items) if hot_items else "> 暂无重磅标记内容"
    reg_str = "\n".join(regular_items) if regular_items else "> 暂无基础金融快讯"
    
    # 顶部数据表
    stat_table = (
        f"| 项目 | 详情 |\n"
        f"| :--- | :--- |\n"
        f"| 📦 聚合总数 | {len(sorted_news)} 条 |\n"
        f"| 🔥 重点推荐 | {len(hot_items)} 条 |\n"
        f"| ⏰ 刷新时间 | {bj_time} |\n"
    )

    desp = (
        f"# 💰 股市全网热点速递\n"
        f"{stat_table}\n"
        f"### 🚩 【今日重磅】\n{hot_str}\n\n"
        f"### 📢 【核心快讯】\n{reg_str}\n\n"
        f"--- \n"
        f"💡 *已大幅降低筛选门槛，确保内容覆盖面。*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市情报|{bj_time}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
