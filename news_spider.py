import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 配置区 ---
RSSHUB_BASE = "https://rss-hub-nu-one.vercel.app" 

FEEDS = {
    "🔥 财新网-财经": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经-热点": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻-证券": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪-快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃新闻-财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📈 经济观察网-股市": f"{RSSHUB_BASE}/eeo/category/11",
    "💰 21世纪经济报道": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "涨停", "跌停", "财报", "利好", "利空", "大盘"]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 正在抓取精选资讯...")
    results = []
    
    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            count = 0
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                # 关键词过滤
                if any(k in title for k in KEYWORDS):
                    count += 1
                    # 精装修格式：标题加粗 + 换行 + 来源
                    results.append(f"### **{title}**\n> 来源：{name}  \n> [点击阅读原文]({link})\n\n---")
            print(f"✅ {name}: 发现 {count} 条相关新闻")
        except Exception as e:
            print(f"❌ {name} 抓取失败: {e}")

    return results

def send_to_server_chan(content_list):
    send_key = os.environ.get('FEISHU_WEBHOOK') # Secrets 里的 SendKey
    
    if not send_key:
        print("❌ 未找到 SendKey")
        return

    # 构造精美的正文
    now_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M') # 转换北京时间
    
    title = f"💰 股市早报 | {now_time}"
    
    if content_list:
        # 使用 Markdown 语法
        header = f"## 📢 今日股票市场情报\n**发布时间：** {now_time}\n\n"
        footer = "\n\n💡 *提示：点击上方链接可跳转原文。资讯仅供参考，不构成投资建议。*"
        desp = header + "\n".join(content_list) + footer
    else:
        desp = f"## 📢 今日股票市场情报\n\n🕒 {now_time}\n\n> 😴 暂未发现包含关键词的重点资讯。"

    # 发送给 Server酱
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    data = {"title": title, "desp": desp}
    
    try:
        response = requests.post(url, data=data)
        print(f"🚀 Server酱 响应: {response.json()}")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    news_items = fetch_news()
    send_to_server_chan(news_items)
