import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区 ---
# 换用一个相对更稳定的公共镜像，或增加容错逻辑
RSSHUB_BASE = "https://rsshub.app" # 也可以尝试你之前的 vercel 节点

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

# 权重关键词：命中这些词，新闻会排到最前面并标记为红旗
CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌", "政策"]
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空", "增持", "减持"]
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间", "视频"]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 正在扫描全网财经热点...")
    news_pool = []
    
    for name, url in FEEDS.items():
        try:
            # 增加超时处理，防止某个源死掉卡住整个程序
            resp = requests.get(url, timeout=15)
            feed = feedparser.parse(resp.text)
            
            if not feed.entries:
                print(f"⚠️ {name} 暂无新内容")
                continue
                
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
        except Exception as e:
            print(f"❌ {name} 抓取超时或失败")
            continue

    # 按标题去重，多源交叉验证的热点大幅提权
    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            unique_news[title]['score'] += 12 # 多个媒体都报了，必是热点
            unique_news[title]['source'] += f"、{item['source']}"

    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, regular_items = [], []
    
    # 核心装修：标题用二级标题(##)，来源和查看用 HTML 的 small 标签（如果平台支持）或列表斜体
    for item in sorted_news[:18]: # 增加到 18 条，覆盖更多网站
        # 使用 - <small> 尝试进一步缩小来源行占位
        source_line = f"- *来源：{item['source']} | [查看全文]({item['link']})*"
        formatted_entry = f"## {item['title']}\n{source_line}\n"
        
        if item['score'] >= 25: # 热度阈值
            hot_items.append(f"🚩 {formatted_entry}")
        else:
            regular_items.append(f"🔹 {formatted_entry}")

    hot_text = "\n".join(hot_items)
    regular_text = "\n".join(regular_items)

    if sorted_news:
        # 统计表头
        stat_header = (
            f"| 维度 | 详情 |\n"
            f"| :--- | :--- |\n"
            f"| 📈 监控来源 | {len(FEEDS)} 个核心媒体 |\n"
            f"| 📦 聚合总数 | {len(sorted_news)} 条精选 |\n"
            f"| 🔥 重点关注 | {len(hot_items)} 条 |\n"
            f"| ⏰ 刷新时间 | {bj_time} |\n\n"
        )
        
        desp = (
            f"# 💰 股市全网热点速递\n"
            f"{stat_header}"
            f"### 🚩 【重磅·热点直击】\n{hot_text if hot_items else '> 暂无超高热度资讯'}\n\n"
            f"### 📢 【核心·市场快讯】\n{regular_text if regular_items else '> 暂无相关资讯聚合'}\n\n"
            f"--- \n"
            f"💡 *以上内容基于多源算法自动去重筛选。*"
        )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    requests.post(url, data={"title": f"股市全网热点|{bj_time}", "desp": desp})

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
