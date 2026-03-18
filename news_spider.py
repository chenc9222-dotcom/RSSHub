import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 配置区 ---
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

# 权重配置
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "茅台", "英伟达", "突破", "暴跌", "暴涨"]
NEGATIVE_KEYWORDS = ["理财", "保险", "领奖", "推广", "开户", "课程", "扫码", "直播", "加群"]

# 稳定图源 (日K线)
MARKET_CHARTS = [
    {"name": "A股 · 上证指数", "url": "https://image.sinajs.cn/newchart/daily/n/sh000001.gif"},
    {"name": "港股 · 恒生指数", "url": "https://image.sinajs.cn/newchart/daily/n/hkHSI.gif"},
    {"name": "美股 · 纳斯达克", "url": "https://image.sinajs.cn/newchart/daily/n/us.ixic.gif"}
]

def fetch_news():
    news_pool = []
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                # 计算热度分
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 15
                if any(k in title for k in ["股票", "A股", "港股", "美股", "财报"]): score += 5
                
                if score > 0:
                    news_pool.append({"title": title, "link": entry.link, "source": name, "score": score})
        except: continue

    # 去重并叠加分值
    unique_news = {}
    for item in news_pool:
        t = item['title']
        if t not in unique_news:
            unique_news[t] = item
        else:
            unique_news[t]['score'] += 10 # 多源报道大幅加分
            unique_news[t]['source'] += f"、{item['source']}"

    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_to_feishu(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: raise ValueError("未获取到环境变量 FEISHU_WEBHOOK")

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 装修看板
    charts = "### 📊 全球大盘看板 (日K)\n"
    for c in MARKET_CHARTS:
        charts += f"**{c['name']}**\n![{c['name']}]({c['url']})\n"

    # 分类内容
    hot, normal = [], []
    for item in sorted_news[:15]:
        content = f"#### **{item['title']}**\n> 来源：`{item['source']}` | [详情]({item['link']})\n---"
        if item['score'] >= 20: hot.append(f"🚩【重点】{content}")
        else: normal.append(content)

    desp = (f"## 💰 股市深度情报箱\n更新时间：{bj_time}\n\n{charts}\n"
            f"### 🎯 今日必看重磅\n{'\n'.join(hot) if hot else '> 暂无超高热度资讯'}\n\n"
            f"### 📢 市场核心快讯\n{'\n'.join(normal)}")

    requests.post(f"https://sctapi.ftqq.com/{send_key}.send", data={"title": f"股市早报|{bj_time}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_to_feishu(data)
