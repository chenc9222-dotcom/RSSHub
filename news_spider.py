import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区 ---
RSSHUB_BASE = "https://rsshub.app" 

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

CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌", "政策"]
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空"]
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间", "视频"]

def fetch_news():
    print("🚀 正在扫描 8 个财经源...")
    news_pool = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    for name, url in FEEDS.items():
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            feed = feedparser.parse(resp.text)
            if not feed.entries:
                continue
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 20
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5
                if score > 0:
                    news_pool.append({"title": title, "link": entry.link, "source": name, "score": score})
        except:
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
    if not send_key:
        print("❌ 缺失 FEISHU_WEBHOOK")
        return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items = []
    regular_items = []
    
    # 分类格式化
    for item in sorted_news[:20]:
        # 满足你要求的格式：标题大(##)，来源小(- *...*)
        content = f"## {item['title']}\n- *来源：{item['source']} | [原文]({item['link']})*\n"
        if item['score'] >= 30:
            hot_items.append(f"🚩 {content}")
        else:
            regular_items.append(f"🔹 {content}")

    # 🎯 核心修复点：预先拼接好字符串，严禁在 f-string {} 内使用反斜杠 \n
    hot_str = "\n".join(hot_items) if hot_items else "> 暂无重磅热点"
    reg_str = "\n".join(regular_items) if regular_items else "> 暂无快讯更新"
    
    # 统计表
    total_count = len(sorted_news)
    hot_count = len(hot_items)
    stat_table = (
        f"| 项目 | 数据 |\n"
        f"| :--- | :--- |\n"
        f"| 📦 聚合总数 | {total_count} |\n"
        f"| 🔥 重磅关注 | {hot_count} |\n"
        f"| ⏰ 刷新时间 | {bj_time} |\n"
    )

    # 组装最终正文
    desp = (
        f"# 💰 股市全网热点速递\n"
        f"{stat_table}\n"
        f"### 🚩 【重磅关注】\n{hot_str}\n\n"
        f"### 📢 【核心快讯】\n{reg_str}\n\n"
        f"--- \n"
        f"💡 *已自动去重筛选，仅供参考。*"
    )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        r = requests.post(url, data={"title": f"全网热点|{bj_time}", "desp": desp})
        print(f"✅ 推送结果: {r.status_code}")
    except Exception as e:
        print(f"❌ 推送报错: {e}")

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
