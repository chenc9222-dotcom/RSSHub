import feedparser
import requests
import os
import re
from datetime import datetime, timedelta

# --- 1. 配置区 ---
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

# 必须包含的词（精准命中）
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "涨停", "跌停", "财报", "IPO", "分红", "研报"]
# 排除掉的垃圾信息（过滤广告或无关内容）
NEGATIVE_KEYWORDS = ["理财产品", "保险", "点击领奖", "推广", "开户福利", "课程", "扫码", "视频"]

def clean_html(raw_html):
    """去除内容中的HTML标签，保持纯净"""
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html)

def fetch_news():
    print(f"[{datetime.now()}] 🚀 正在深度筛选精准资讯...")
    results = []
    seen_titles = set() # 防止不同来源抓到重复新闻

    for name, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            if not feed.entries: continue

            for entry in feed.entries:
                title = entry.title.strip()
                link = entry.link
                
                # 逻辑过滤：包含正面词 且 不含负面词 且 没抓过
                is_target = any(k in title for k in POSITIVE_KEYWORDS)
                is_trash = any(k in title for k in NEGATIVE_KEYWORDS)
                
                if is_target and not is_trash and title not in seen_titles:
                    seen_titles.add(title)
                    # 装修每条新闻的显示格式
                    results.append(
                        f"#### **{title}**\n"
                        f"> **来源**：`{name}`\n"
                        f"> [立即查阅详情]({link})\n"
                        f"---"
                    )
        except Exception as e:
            print(f"❌ {name} 获取失败: {e}")

    return results

def send_to_server_chan(content_list):
    send_key = os.environ.get('FEISHU_WEBHOOK') 
    if not send_key: return

    # 北京时间处理 (GitHub Actions 默认是 UTC)
    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    title = f"📈 股市早报 | {bj_time}"
    
    if content_list:
        # 组装精美的正文
        header = (
            f"### 🎯 深度筛选：今日股市精华\n"
            f"**更新时间**：{bj_time}\n"
            f"**情报数量**：共计 {len(content_list)} 条精选\n\n"
            f"![Header](https://images.unsplash.com/photo-1611974717482-58a0000ad5bc?auto=format&fit=crop&q=80&w=400)\n\n"
        )
        footer = (
            f"\n\n---\n"
            f"📢 *注：已自动过滤冗余推广信息。资讯由机器人自动聚合，仅供参考。*"
        )
        desp = header + "\n".join(content_list) + footer
    else:
        desp = f"### 🎯 深度筛选：今日股市精华\n\n🕒 {bj_time}\n\n> 💡 暂无高价值实时波动，市场相对平稳。"

    # 推送
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        requests.post(url, data={"title": title, "desp": desp})
        print(f"✅ 精修版消息已发出，共 {len(content_list)} 条资讯。")
    except Exception as e:
        print(f"❌ 发送失败: {e}")

if __name__ == "__main__":
    news_items = fetch_news()
    send_to_server_chan(news_items)
