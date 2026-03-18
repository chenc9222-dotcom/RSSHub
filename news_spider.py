import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区 ---
# 更换为更稳定的镜像站节点
RSSHUB_BASE = "https://rsshub.icu" 

FEEDS = {
    "🔥 财新网": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📈 东方财富": f"{RSSHUB_BASE}/eastmoney/report/strategy",
    "💰 21世纪经济": f"{RSSHUB_BASE}/21jingji/channel/investment",
    "🌐 华尔街见闻": f"{RSSHUB_BASE}/wallstreetcn/news/global"
}

# 调低门槛，确保有内容输出
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌", "政策"]
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空", "大跌", "反弹"]
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间", "视频"]

def fetch_news():
    print("🚀 启动深度扫描模式...")
    news_pool = []
    # 模拟真实浏览器，防止屏蔽
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    for name, url in FEEDS.items():
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code != 200: continue
            
            feed = feedparser.parse(resp.text)
            if not feed.entries: continue
            
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                # 重新计算权重：即使没中关键词，只要有相关性就给基础分
                score = 5 
                if any(k in title for k in CORE_KEYWORDS): score += 20
                if any(k in title for k in POSITIVE_KEYWORDS): score += 10
                
                news_pool.append({
                    "title": title, 
                    "link": entry.link, 
                    "source": name, 
                    "score": score
                })
            print(f"✅ {name} 抓取成功")
        except:
            print(f"❌ {name} 连接超时")
            continue

    unique_news = {}
    for item in news_pool:
        t = item['title']
        if t not in unique_news:
            unique_news[t] = item
        else:
            unique_news[t]['score'] += 15
            unique_news[t]['source'] += f"、{item['source']}"

    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, regular_items = [], []
    
    # 调整分类阈值：25分以上为红旗，其余为普通
    for item in sorted_news[:20]:
        content = f"## {item['title']}\n- *来源：{item['source']} | [原文]({item['link']})*\n"
        if item['score'] >= 25:
            hot_items.append(f"🚩 {content}")
        else:
            regular_items.append(f"🔹 {content}")

    hot_str = "\n".join(hot_items) if hot_items else "> 当前暂无超高权重热点"
    reg_str = "\n".join(regular_items) if regular_items else "> 正在等待市场动态更新"
    
    stat_table = (
        f"| 项目 | 详情 |\n"
        f"| :--- | :--- |\n"
        f"| 📈 监控渠道 | {len(FEEDS)} 个核心网站 |\n"
        f"| 📦 聚合总数 | {len(sorted_news)} 条 |\n"
        f"| 🔥 重点推荐 | {len(hot_items)} 条 |\n"
        f"| ⏰ 刷新时间 | {bj_time} |\n"
    )

    desp = (
        f"# 💰 股市全网热点速递\n"
        f"{stat_table}\n"
        f"### 🚩 【重磅关注】\n{hot_str}\n\n"
        f"### 📢 【核心快讯】\n{reg_str}\n\n"
        f"--- \n"
        f"💡 *以上内容根据多源算法实时筛选，仅供参考。*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市情报|{bj_time}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
