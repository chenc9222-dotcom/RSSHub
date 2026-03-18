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

# 权重关键词
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌"]
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空", "增持", "减持"]
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间"]

def fetch_news():
    news_pool = []
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 15
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5
                
                if score > 0:
                    news_pool.append({
                        "title": title,
                        "link": entry.link,
                        "source": name,
                        "score": score
                    })
        except: continue

    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            unique_news[title]['score'] += 10
            unique_news[title]['source'] += f"、{item['source']}"

    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key:
        print("❌ 未读取到 Secret 变量")
        return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    hot_items = []
    regular_items = []
    
    for item in sorted_news[:15]:
        # 装修：标题用 ## (大)，来源用 > (小且灰)
        formatted_entry = f"## {item['title']}\n> {item['source']} | [查看]({item['link']})\n---"
        
        if item['score'] >= 20:
            hot_items.append(f"🚩 {formatted_entry}")
        else:
            regular_items.append(f"🔹 {formatted_entry}")

    # 预拼接
    hot_text = "\n".join(hot_items)
    regular_text = "\n".join(regular_items)

    # 组装消息
    if not sorted_news:
        desp = f"# 💰 股市早报 | {bj_time}\n\n> 今日暂无符合条件的重点资讯。"
    else:
        # 顶部统计区
        stat_header = (
            f"| 统计维度 | 数据统计 |\n"
            f"| :--- | :--- |\n"
            f"| 📊 聚合总数 | {len(sorted_news)} 条 |\n"
            f"| 🔥 重磅热点 | {len(hot_items)} 条 |\n"
            f"| 📅 更新时间 | {bj_time} |\n\n"
        )
        
        desp = (
            f"# 💰 股市情报快报\n"
            f"{stat_header}"
            f"### 🚩 今日重磅关注\n"
            f"{hot_text if hot_items else '> 暂无超高热度资讯'}\n\n"
            f"### 📢 市场核心资讯\n"
            f"{regular_text if regular_items else '> 暂无相关资讯聚合'}\n\n"
            f"--- \n"
            f"💡 *已自动过滤冗余推广，仅保留核心市场动态。*"
        )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        requests.post(url, data={"title": f"早报|{bj_time}", "desp": desp})
        print(f"✅ 推送完成")
    except Exception as e:
        print(f"❌ 失败: {e}")

if __name__ == "__main__":
    final_news = fetch_news()
    send_message(final_news)
