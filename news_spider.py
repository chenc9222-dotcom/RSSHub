import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 配置区 ---
# 确保这是你 Vercel 部署成功的 RSSHub 域名
RSSHUB_BASE = "https://rss-hub-nu-one.vercel.app" 

FEEDS = {
    "财新网-财经": f"{RSSHUB_BASE}/caixin/finance/charge",
    "第一财经-热点": f"{RSSHUB_BASE}/yicai/brief",
    "界面新闻-证券": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "36氪-快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "澎湃新闻-财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "经济观察网-股市": f"{RSSHUB_BASE}/eeo/category/11",
    "21世纪经济报道-投资": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

# 过滤关键词
KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "涨停", "跌停", "财报", "利好", "利空"]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 开始抓取股票资讯...")
    results = []
    
    # 获取 24 小时内的新闻
    cutoff_time = datetime.utcnow() - timedelta(days=1)
    
    for name, url in FEEDS.items():
        try:
            print(f"正在读取: {name}...")
            feed = feedparser.parse(url)
            
            if not feed.entries:
                continue

            for entry in feed.entries:
                title = entry.title
                link = entry.link
                # 关键词过滤
                if any(k in title for k in KEYWORDS):
                    results.append(f"### {name}\n**{title}**\n[查看详情]({link})\n")
        except Exception as e:
            print(f"读取 {name} 出错: {e}")

    return results

def send_to_server_chan(content_list):
    """通过 Server酱 发送消息"""
    # 这里的 FEISHU_WEBHOOK 变量在 GitHub Secrets 里应该填入你的 Server酱 SendKey (SCT...)
    send_key = os.environ.get('FEISHU_WEBHOOK')
    
    if not send_key:
        print("❌ 错误: 未在 GitHub Secrets 中找到 SendKey (FEISHU_WEBHOOK)")
        return

    title = f"📈 每日股票资讯汇总 ({datetime.now().strftime('%Y-%m-%d')})"
    
    if content_list:
        desp = "\n\n".join(content_list)
    else:
        desp = "今日暂无符合关键词的股票资讯。"

    # Server酱 Turbo 版接口
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    data = {
        "title": title,
        "desp": desp
    }
    
    try:
        response = requests.post(url, data=data)
        result = response.json()
        print(f"✅ Server酱 响应结果: {result}")
    except Exception as e:
        print(f"❌ 推送至 Server酱 失败: {e}")

if __name__ == "__main__":
    news_items = fetch_news()
    print(f"📊 共抓取到 {len(news_items)} 条相关新闻")
    send_to_server_chan(news_items)
