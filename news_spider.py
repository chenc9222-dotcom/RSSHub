import feedparser
import requests
import os
from datetime import datetime, timedelta

# --- 1. 配置区 ---
# 建议使用官方地址，或更换备用镜像提高抓取成功率
RSSHUB_BASE = "https://rsshub.app" 

FEEDS = {
    "🔥 财新网": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📉 东方财富": f"{RSSHUB_BASE}/eastmoney/report/strategy",
    "💰 21世纪经济": f"{RSSHUB_BASE}/21jingji/channel/investment",
    "🌐 华尔街见闻": f"{RSSHUB_BASE}/wallstreetcn/news/global"
}

CORE_KEYWORDS = ["重磅", "紧急", "降息", "加息", "腾讯", "阿里", "美团", "茅台", "英伟达", "突破", "暴涨", "暴跌", "政策"]
POSITIVE_KEYWORDS = ["股票", "A股", "港股", "美股", "证券", "上市", "财报", "利好", "利空"]
NEGATIVE_KEYWORDS = ["理财产品", "保险", "领奖", "推广", "开户福利", "课程", "扫码", "直播间", "视频"]

def fetch_news():
    print(f"[{datetime.now()}] 🚀 正在深度扫描 8 个核心财经源...")
    news_pool = []
    
    for name, url in FEEDS.items():
        try:
            # 增加 Headers 模拟浏览器，减少被屏蔽几率
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            resp = requests.get(url, headers=headers, timeout=20)
            feed = feedparser.parse(resp.text)
            
            if not feed.entries:
                print(f"⚪ {name}: 暂无新内容")
                continue
                
            for entry in feed.entries:
                title = entry.title.strip()
                if any(k in title for k in NEGATIVE_KEYWORDS): continue
                
                score = 0
                if any(k in title for k in CORE_KEYWORDS): score += 20
                if any(k in title for k in POSITIVE_KEYWORDS): score += 5
                
                if score > 0:
                    news_pool.append({"title": title, "link": entry.link, "source": name, "score": score})
            print(f"✅ {name}: 抓取成功")
        except Exception as e:
            print(f"❌ {name}: 访问失败")
            continue

    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            unique_news[title]['score'] += 15 # 多源报道大幅提权
            unique_news[title]['source'] += f"、{item['source']}"

    return sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key: return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    hot_items, regular_items = [], []
    
    # 分类处理
    for item in sorted_news[:20]:
        # 视觉降级：来源行使用列表+斜体+括号，不使用引用块
        source_line = f"- *(来源：{item['source']} | [原文]({item['link']}))*"
        # 标题加粗加亮
        formatted_entry = f"## {item['title']}\n{source_line}\n"
        
        if item['score'] >= 30:
            hot_items.append(f"🚩 {formatted_entry}")
        else:
            regular_items.append(f"🔹 {formatted_entry}")

    # 预设统计信息
    stat_header = (
        f"| 项目 | 数据内容 |\n"
        f"| :--- | :--- |\n"
        f"| 📈 监控渠道 | {len(FEEDS)} 个核心网站 |\n"
        f"| 📦 聚合总数 | {len(sorted_news)} 条精选 |\n"
        f"| 🔥 热点重磅 | {len(hot_items)} 条 |\n"
        f"| ⏰ 刷新时间 | {bj_time} |\n\n"
    )

    # 🎯 修复点：初始化 desp，防止暂无新闻时报错
    if not sorted_news:
        desp = f"# 💰 股市热点速递\n{stat_header}\n\n> 💡 今日此时暂无高价值市场资讯。"
    else:
        desp = (
            f"# 💰 股市全网热点速递\n"
            f"{stat_header}"
            f"### 🚩 【重磅热点直击】\n{'\n'.join(hot_items) if hot_items else '> 暂无超高权重热点'}\n\n"
            f"### 📢 【核心市场快讯】\n{'\n'.join(regular_items) if regular_items else '> 暂无相关资讯聚合'}\n\n"
            f"--- \n"
            f"💡 *已自动去重筛选，点击“原文”可查看详情。*"
        )

    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        requests.post(url, data={"title": f"全网热点|{bj_time}", "desp": desp})
        print(f"🚀 推送成功：共 {len(sorted_news)} 条新闻")
    except Exception as e:
        print(f"❌ 推送失败: {e}")

if __name__ == "__main__":
    data = fetch_news()
    send_message(data)
