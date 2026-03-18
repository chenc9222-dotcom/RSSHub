import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区：直接使用官方原始源，绕过不稳定的第三方镜像 ---
FEEDS = {
    "🔥 财新网": "https://feeds.feedburner.com/caixin",
    "📢 第一财经": "https://www.yicai.com/rss",
    "⚡ 36氪快讯": "https://36kr.com/feed",
    "📈 东方财富": "https://fund.eastmoney.com/rss/cp_scgd.xml",
    "💰 21世纪": "https://www.21jingji.com/rss/investment.xml"
}

# 极致降低门槛：只要有金融相关字眼就抓
BASE_KEYWORDS = ["股", "市", "金", "财", "债", "经", "报", "美", "港", "A"]
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "利好", "利空", "突破", "爆料"]

def fetch_news():
    print("🚀 启动原始源直接对撞模式...")
    news_pool = []
    # 深度伪装成 macOS 浏览器，绕过 Actions 的脚本标识
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Accept': 'application/xml,text/xml,*/*'
    }
    
    for name, url in FEEDS.items():
        try:
            # 增加 verify=False 防止 SSL 证书报错导致抓取中断
            resp = requests.get(url, headers=headers, timeout=20, verify=False)
            feed = feedparser.parse(resp.text)
            
            if not feed.entries:
                print(f"⚪ {name}: 未获取到条目")
                continue
                
            for entry in feed.entries:
                title = entry.title.strip()
                # 统计评分
                score = 5
                if any(k in title for k in BASE_KEYWORDS): score += 10
                if any(k in title for k in CORE_KEYWORDS): score += 20
                
                # 只要不是 0 分就全都要
                news_pool.append({
                    "title": title, 
                    "link": entry.link, 
                    "source": name, 
                    "score": score
                })
            print(f"✅ {name}: 成功抓取到内容")
        except:
            print(f"❌ {name}: 连接失败")
            continue

    unique_news = {}
    for item in news_pool:
        t = item['title']
        if t not in unique_news:
            unique_news[t] = item
    
    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, regular_items = [], []
    
    # 精选前 20 条
    for item in sorted_news[:20]:
        # 按照你的要求：标题巨醒目，来源极其小
        source_line = f"- *(来源：{item['source']} | [原文]({item['link']}))*"
        formatted_entry = f"## {item['title']}\n{source_line}\n"
        
        if item['score'] >= 25:
            hot_items.append(f"🚩 {formatted_entry}")
        else:
            regular_items.append(f"🔹 {formatted_entry}")

    # 预拼接（解决 Python 语法错误问题）
    hot_str = "\n".join(hot_items) if hot_items else "> 暂无超高权重资讯"
    reg_str = "\n".join(regular_items) if regular_items else "> 暂无基础资讯"
    
    stat_table = (
        f"| 项目 | 实时汇总 |\n"
        f"| :--- | :--- |\n"
        f"| 📈 原始源 | {len(FEEDS)} 个 |\n"
        f"| 📦 聚合总数 | {len(sorted_news)} 条 |\n"
        f"| ⏰ 刷新时间 | {bj_time} |\n\n"
    )

    desp = (
        f"# 💰 股市全网热点速递\n"
        f"{stat_table}"
        f"### 🚩 【重磅关注】\n{hot_str}\n\n"
        f"### 📢 【核心快讯】\n{reg_str}\n\n"
        f"--- \n"
        f"💡 *已改用原始数据源直接抓取，确保内容产出。*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市情报|{bj_time}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
