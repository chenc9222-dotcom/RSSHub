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

# 精准正面词
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "涨停", "跌停", "财报", "IPO", "分红", "利好", "利空"]
# 垃圾信息负面词（过滤广告和无关内容）
NEGATIVE_KEYWORDS = ["理财产品", "保险", "点击领奖", "推广", "开户福利", "课程", "扫码", "视频", "直播间"]

# 动态行情图接口（新浪财经提供，实时更新）
MARKET_CHARTS = [
    {"name": "上证指数 (A股)", "url": "https://image.sinajs.cn/newchart/min/n/sh000001.gif"},
    {"name": "恒生指数 (港股)", "url": "https://image.sinajs.cn/newchart/min/n/hkHSI.gif"},
    {"name": "纳斯达克 (美股)", "url": "https://image.sinajs.cn/newchart/min/n/us.ixic.gif"}
]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 启动深度筛选模式...")
    results = []
    seen_titles = set() # 去重逻辑

    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            for entry in feed.entries:
                title = entry.title.strip()
                link = entry.link
                
                # 逻辑过滤
                is_target = any(k in title for k in POSITIVE_KEYWORDS)
                is_trash = any(k in title for k in NEGATIVE_KEYWORDS)
                
                if is_target and not is_trash and title not in seen_titles:
                    seen_titles.add(title)
                    # 装修新闻条目
                    results.append(f"#### **{title}**\n> 来源：`{name}` | [点击查阅]({link})\n---")
        except Exception as e:
            print(f"❌ {name} 抓取失败: {e}")

    return results

def send_to_server_chan(content_list):
    send_key = os.environ.get('FEISHU_WEBHOOK') 
    if not send_key:
        print("❌ 错误：未找到 SendKey")
        return

    # 转换北京时间
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 构造“精装修”报表
    title = f"📊 股市深度情报 | {bj_time}"
    
    # 1. 顶部：行情对比图部分
    chart_section = "### 📈 实时大盘对比\n"
    for chart in MARKET_CHARTS:
        chart_section += f"**{chart['name']}**\n![{chart['name']}]({chart['url']})\n"
    
    chart_section += "\n---\n"

    # 2. 中间：统计表格
    stats_table = (
        f"| 维度 | 数据内容 |\n"
        f"| :--- | :--- |\n"
        f"| 更新时间 | {bj_time} |\n"
        f"| 精选数量 | {len(content_list)} 条 |\n"
        f"| 状态 | ✅ 已过滤冗余信息 |\n\n"
    )

    # 3. 底部：新闻正文
    if content_list:
        main_news = "### 🎯 核心新闻精选\n" + "\n".join(content_list)
    else:
        main_news = "### 🎯 核心新闻精选\n\n> 💡 暂无高价值波动，建议观察大盘走势。"

    # 汇总
    desp = f"## 💰 每日金融看板\n" + chart_section + stats_table + main_news + "\n\n📢 *风险提示：资讯均由 AI 聚合，不构成投资建议。*"

    # 发送请求
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        resp = requests.post(url, data={"title": title, "desp": desp})
        print(f"✅ 发送成功！响应：{resp.json()}")
    except Exception as e:
        print(f"❌ 发送失败：{e}")

if __name__ == "__main__":
    news_data = fetch_news()
    send_to_server_chan(news_data)
