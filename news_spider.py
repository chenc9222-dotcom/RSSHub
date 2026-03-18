import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区 ---
RSSHUB_BASE = "https://rss-hub-nu-one.vercel.app" 

FEEDS = {
    "🔥 财新网财经": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经热点": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻证券": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📈 经观股市": f"{RSSHUB_BASE}/eeo/category/11",
    "💰 21世纪经济": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

# 【重点关注词】命中核心词权重翻倍
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌"]
# 【普通关键词】
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空", "增持", "减持"]
# 【负面垃圾词】
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间"]

# 走势图接口 (静态日K线图，兼容性最好)
MARKET_CHARTS = [
    {"name": "A股 · 上证指数 (sh000001)", "url": "https://image.sinajs.cn/newchart/daily/n/sh000001.gif"},
    {"name": "港股 · 恒生指数 (hkHSI)", "url": "https://image.sinajs.cn/newchart/daily/n/hkHSI.gif"},
    {"name": "美股 · 纳斯达克 (us.ixic)", "url": "https://image.sinajs.cn/newchart/daily/n/us.ixic.gif"}
]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 启动智能筛选与热点权重分析...")
    news_pool = []
    
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                # 计算初始评分
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 15 # 核心词+15
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5 # 普通词+5
                
                if score > 0:
                    news_pool.append({
                        "title": title,
                        "link": entry.link,
                        "source": name,
                        "score": score
                    })
        except: continue

    # 按标题去重，多源报道则增加权重
    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            # 多个来源同时报道同一条新闻，判定为“热点”
            unique_news[title]['score'] += 10
            unique_news[title]['source'] += f"、{item['source']}"

    # 按分数排序
    sorted_news = sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)
    return sorted_news

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key:
        print("❌ 错误：未读取到 Secret 变量")
        return

    # 转换北京时间
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 看板装修
    chart_section = "### 📊 全球指数稳定看板 (日K)\n"
    for chart in MARKET_CHARTS:
        chart_section += f"**{chart['name']}**\n![{chart['name']}]({chart['url']})\n"
    
    chart_section += "\n---\n"

    # 分类和格式化内容
    hot_items = []
    regular_items = []
    
    for item in sorted_news[:15]:
        formatted_entry = f"#### **{item['title']}**\n> 来源：{item['source']} | [点击查阅链接]({item['link']})\n---"
        
        # 定义核心热度分界线（评分过20分定为重磅）
        if item['score'] >= 20:
            hot_items.append(f"🔴 【重点】{formatted_entry}")
        else:
            regular_items.append(formatted_entry)

    # 🎯 核心修复：预先拼接字符串，避免在f-string内使用反斜杠
    # 这样写保证在Python 3.9环境下完美运行！
    hot_text = "\n".join(hot_items)
    regular_text = "\n".join(regular_items)

    # 完整拼接消息正文
    if not sorted_news:
        desp = f"## 💰 每日金融早报\n更新时间：{bj_time}\n\n{chart_section}\n\n> 今日暂无核心符合的重磅或普通资讯。"
    else:
        desp = (
            f"## 💰 每日金融情报箱\n"
            f"**更新时间**：{bj_time} (北京)\n\n"
            f"{chart_section}"
            f"### 🚩 今日必看重磅热点\n"
            f"{hot_text if hot_items else '> 暂无超高权重热点，市场相对平稳。'}\n\n"
            f"### 📢 更多核心市场快讯\n"
            f"{regular_text if regular_items else '> 暂无相关资讯聚合。'}\n\n"
            f"--- \n"
            f"⚠️ *风险提示：资讯聚合自公开网络，不代表投资建议。市场有风险，入市需谨慎。*"
        )

    # 发送
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        requests.post(url, data={"title": f"股市早报 | {bj_time}", "desp": desp})
        print(f"✅ 完成筛选与推送，共筛选资讯 {len(sorted_news)} 条。")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    final_news = fetch_news()
    send_message(final_news)
