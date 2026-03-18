import feedparser
import requests
import json
import os
from datetime import datetime, timedelta

# --- 配置区 ---
# 使用你刚刚在 Vercel 部署的地址，或者 RSSHub 官方地址
RSSHUB_BASE = "https://rsshub.app" 

# 订阅源字典 (RSSHub 路由)
FEEDS = {
    "财新网-财经": f"{RSSHUB_BASE}/caixin/finance/charge",
    "第一财经-热点": f"{RSSHUB_BASE}/yicai/brief",
    "界面新闻-证券": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "36氪-快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "澎湃新闻-财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "经济观察网-股市": f"{RSSHUB_BASE}/eeo/category/11",
    "21世纪经济报道-投资": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

# 过滤关键词（包含这些才留下）
KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "涨停", "跌停", "财报", "利好", "利空"]
# 垃圾信息过滤（包含这些则剔除）
TRASH_WORDS = ["广告", "推广", "理财产品"]

def fetch_news():
    print(f"[{datetime.now()}] 开始抓取流程...")
    results = []
    
    for name, url in FEEDS.items():
        try:
            print(f"正在抓取: {name}...")
            feed = feedparser.parse(url)
            
            # 只取最近 24 小时的新闻
            cutoff_time = datetime.utcnow() - timedelta(days=1)
            
            for entry in feed.entries:
                title = entry.title
                link = entry.link
                summary = entry.get('summary', '')
                
                # 关键词匹配逻辑
                is_stock = any(k in title or k in summary for k in KEYWORDS)
                is_trash = any(t in title for t in TRASH_WORDS)
                
                if is_stock and not is_trash:
                    results.append(f"【{name}】\n标题：{title}\n链接：{link}\n")
        except Exception as e:
            print(f"❌ {name} 抓取失败: {str(e)}")

    print(f"抓取完成，共获得 {len(results)} 条相关新闻。")
    return results

def send_to_feishu(content_list):
    webhook_url = os.environ.get('FEISHU_WEBHOOK')
    if not webhook_url:
        print("❌ 未找到 FEISHU_WEBHOOK 环境变量")
        return

    # 分段发送，防止内容过长
    full_content = "\n".join(content_list) if content_list else "今日暂无重点股票资讯。"
    
    payload = {
        "msg_type": "text",
        "content": {
            "text": f"📢 每日股票市场资讯汇总 ({datetime.now().strftime('%Y-%m-%d')})\n\n{full_content}"
        }
    }
    
    try:
        resp = requests.post(webhook_url, json=payload)
        print(f"推送结果: {resp.text}")
    except Exception as e:
        print(f"❌ 推送失败: {str(e)}")

if __name__ == "__main__":
    news = fetch_news()
    send_to_feishu(news)
    print("--- 调试信息：脚本运行结束 ---")
