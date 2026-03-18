import feedparser
import requests
import os
import re
from datetime import datetime, timedelta

# --- 1. 配置区 ---
RSSHUB_BASE = "https://rss-hub-nu-one.vercel.app" 

FEEDS = {
    "🔥 财新网": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📈 经观股市": f"{RSSHUB_BASE}/eeo/category/11",
    "💰 21世纪经济": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

# 【重点关注词】命中这些词，权重翻倍
CORE_KEYWORDS = ["重磅", "紧急", "首份", "突破", "暴跌", "暴涨", "停牌", "破产", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达"]
# 【普通关键词】
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "IPO", "利好", "利空", "增持", "减持"]
# 【负面垃圾词】
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间", "加群"]

# 走势图接口
MARKET_CHARTS = [
    {"name": "上证指数 (A股)", "url": "https://image.sinajs.cn/newchart/min/n/sh000001.gif"},
    {"name": "恒生指数 (港股)", "url": "https://image.sinajs.cn/newchart/min/n/hkHSI.gif"},
    {"name": "纳斯达克 (美股)", "url": "https://image.sinajs.cn/newchart/min/n/us.ixic.gif"}
]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 启动智能热点分析模式...")
    news_pool = []
    
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                # 计算“热力值”
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 10 # 核心词+10
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5 # 普通词+5
                
                if score > 0:
                    news_pool.append({
                        "title": title,
                        "link": entry.link,
                        "source": name,
                        "score": score
                    })
        except: continue

    # 1. 按标题去重
    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            # 如果多个来源都有，增加热力值
            unique_news[title]['score'] += 8
            unique_news[title]['source'] += f"、{item['source']}"

    # 2. 按分值排序
    sorted_news = sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)
    return sorted_news

def format_content(sorted_news):
    hot_news = []
    regular_news = []
    
    for item in sorted_news:
        formatted = f"#### **{item['title']}**\n> 来源：{item['source']} | [阅读全文]({item['link']})\n"
        # 评分超过15分的定义为“重点热点”
        if item['score'] >= 15:
            hot_news.append(f"🚩【重磅】{formatted}")
        else:
            regular_news.append(formatted)
            
    return hot_news[:5], regular_news[:10] # 重点前5条，普通前10条

def send_message(hot, regular):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 装修布局
    chart_section = "### 📊 全球大盘实时看板\n"
    for chart in MARKET_CHARTS:
        chart_section += f"**{chart['name']}**\n![{chart['name']}]({chart['url']})\n"

    hot_section = "## 🔴 今日必看重磅热点\n" + "\n".join(hot) if hot else ""
    regular_section = "## 🔵 更多重要市场资讯\n" + "\n".join(regular) if regular else ""
    
    desp = f"## 💰 每日金融情报箱\n更新时间：{bj_time}\n\n{chart_section}\n---\n{hot_section}\n\n---\n{regular_section}"
    
    requests.post(f"https://sctapi.ftqq.com/{send_key}.send", data={"title": f"股市早报 | {bj_time}", "desp": desp})

if __name__ == "__main__":
    all_news = fetch_news()
    hot, regular = format_content(all_news)
    send_message(hot, regular)
