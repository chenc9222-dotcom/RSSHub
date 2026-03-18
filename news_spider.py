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

# 核心重点词 (加分项)
CORE_KEYWORDS = ["重磅", "紧急", "突破", "降息", "加息", "腾讯", "阿里", "茅台", "英伟达", "低空经济", "人工智能"]
# 普通关键词
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空"]
# 垃圾负面词
NEGATIVE_KEYWORDS = ["理财产品", "开户福利", "推广", "课程", "扫码", "直播间", "视频页"]

# 2. 【核心修改】全球市场动态图表链接（全部更换为更稳定的日K线图接口）
# K线图直链由于是非动态的，防盗链几率和失效几率极低，稳定性极强。
MARKET_CHARTS = [
    {
        "name": "A股 · 上证指数 (sh000001) 日K", 
        "url": "https://image.sinajs.cn/newchart/daily/n/sh000001.gif"
    },
    {
        "name": "港股 · 恒生指数 (hkHSI) 日K", 
        "url": "https://image.sinajs.cn/newchart/daily/n/hkHSI.gif"
    },
    {
        "name": "美股 · 纳斯达克 (us.ixic) 日K", 
        "url": "https://image.sinajs.cn/newchart/daily/n/us.ixic.gif"
    }
]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 启动精选聚合分析模式...")
    news_pool = []
    
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                # 精准评分逻辑
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 10
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5
                
                if score > 0:
                    news_pool.append({
                        "title": title,
                        "link": entry.link,
                        "source": name,
                        "score": score
                    })
        except: continue

    # 按标题深度去重，多源报告则增加热度
    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            unique_news[title]['score'] += 8
            unique_news[title]['source'] = f"{unique_news[title]['source']}、{item['source']}"

    # 按分数排序并返回
    sorted_news = sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)
    return sorted_news

def send_message(all_news):
    send_key = os.environ.get('FEISHU_WEBHOOK') 
    if not send_key:
        print("❌ 错误：未找到 FEISHU_WEBHOOK (SendKey)")
        return

    # 转换北京时间
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 1. 看板装修：全球核心指数稳定日K线图
    chart_section = "### 📊 全球指数稳定看板 (日K)\n"
    for chart in MARKET_CHARTS:
        # Markdown写法：如果图片挂了，至少会显示名称和链接
        chart_section += f"**{chart['name']}**\n![{chart['name']}]({chart['url']})\n"
    
    chart_section += "\n---\n"

    # 2. 资讯分级
    hot_content = []
    regular_content = []
    
    for item in all_news[:15]: # 只看排名前15的新闻
        # 精美装修：标题加粗 + 来源
        formatted_entry = f"#### **{item['title']}**\n> 来源：`{item['source']}` | [点击查阅原文]({item['link']})\n---"
        
        # 核心重点热点（评分过15分，打红色星号）
        if item['score'] >= 15:
            hot_content.append(f"🔴 【重点】{formatted_entry}")
        else:
            regular_content.append(f"🔵 【资讯】{formatted_entry}")

    # 3. 正文拼接
    if not all_news:
        desp = f"## 💰 每日金融早报\n更新时间：{bj_time}\n\n{chart_section}\n\n> 今日暂无符合条件的财经资讯。"
    else:
        desp = (
            f"## 💰 每日金融情报箱\n"
            f"**更新时间**：{bj_time} (北京)\n\n"
            f"{chart_section}"
            f"### 🚩 今日重点重磅热点\n"
            f"{'暂无热点资讯。' if not hot_content else '\n'.join(hot_content)}\n\n"
            f"### 📢 更多核心市场快讯\n"
            f"{'暂无资讯。' if not regular_content else '\n'.join(regular_content)}"
        )

    # 发送
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市早报 | {bj_time}", "desp": desp})
    print(f"✅ 完成筛选与推送，共推送新闻 {len(all_news)} 条。")

if __name__ == "__main__":
    final_news = fetch_news()
    send_message(final_news)
