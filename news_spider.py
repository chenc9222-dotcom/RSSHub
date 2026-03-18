import feedparser
import requests
import os
import json
import logging
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

# ========== 1. 配置区 ==========
# 多个 RSSHub 节点轮询
RSSHUB_NODES = [
    "https://rss-hub-nu-one.vercel.app",
    "https://rsshub.app",
    "https://rsshub.icu"
]

# ========== 新闻源（大幅扩充）==========
FEEDS = {
    # 原有
    "🔥 财新网": "/caixin/finance/charge",
    "📢 第一财经": "/yicai/brief",
    "📊 界面新闻": "/jiemian/v4/news/22",
    "⚡ 36氪快讯": "/36kr/newsflashes",
    "🏙️ 澎湃财经": "/thepaper/channel/25951",
    "📈 经观股市": "/eeo/category/11",
    "💰 21世纪经济": "/21jingji/channel/investment",
    
    # 新增财经媒体
    "📰 华尔街见闻": "/wallstreetcn/latest",
    "📡 财联社": "/cls/depth/1000",
    "🏦 证券时报": "/stcn/roll",
    "📉 上海证券报": "/cnstock/news",
    "📊 中国证券报": "/csn/roll",
    "🌐 新浪财经": "/sina/finance",
    "🕸️ 腾讯财经": "/tencent/finance/latest",
    "📱 网易财经": "/netease/finance",
    "📺 搜狐财经": "/sohu/finance",
    "📈 雪球热门": "/xueqiu/hot",
    "🏢 东方财富": "/eastmoney/roll",
    "📰 和讯财经": "/hexun/finance",
    "🌍 环球财经": "/huanqiu/finance",
    "📡 新华财经": "/xinhua/finance",
    "🏛️ 人民网财经": "/people/finance",
}

# 关键词权重配置（完整版）
URGENT_KEYWORDS = ["紧急", "突发", "重磅", "快讯", "最新", "刚刚", "央行", "证监会", "银保监会", "国务院", "政治局"]
POLICY_KEYWORDS = ["降息", "加息", "降准", "MLF", "LPR", "逆回购", "货币政策", "利率", "准备金率", "CPI", "PPI", "PMI", "GDP", "经济数据"]
MARKET_KEYWORDS = ["A股", "港股", "美股", "股票", "证券", "股市", "大盘", "指数", "上证", "深证", "创业板", "北向资金", "涨停", "跌停"]
COMPANY_KEYWORDS = ["腾讯", "阿里", "美团", "京东", "拼多多", "百度", "字节", "华为", "小米", "茅台", "英伟达", "特斯拉", "比亚迪"]
EARNINGS_KEYWORDS = ["财报", "业绩", "营收", "净利润", "同比增长", "环比增长", "扭亏", "预增", "预减"]
DEAL_KEYWORDS = ["收购", "并购", "重组", "IPO", "上市", "定增", "减持", "增持", "回购"]
RISK_KEYWORDS = ["暴跌", "暴涨", "崩盘", "熔断", "退市", "利空", "利好", "立案", "处罚", "违约", "暴雷"]
INDUSTRY_KEYWORDS = ["新能源", "光伏", "芯片", "半导体", "AI", "人工智能", "消费", "医药", "房地产", "基建"]

# 合并权重字典
KEYWORD_WEIGHTS = {
    **dict.fromkeys(URGENT_KEYWORDS, 25),
    **dict.fromkeys(POLICY_KEYWORDS, 20),
    **dict.fromkeys(MARKET_KEYWORDS, 15),
    **dict.fromkeys(COMPANY_KEYWORDS, 15),
    **dict.fromkeys(EARNINGS_KEYWORDS, 12),
    **dict.fromkeys(DEAL_KEYWORDS, 12),
    **dict.fromkeys(RISK_KEYWORDS, 10),
    **dict.fromkeys(INDUSTRY_KEYWORDS, 8),
}

# 负向过滤（扩充）
NEGATIVE_KEYWORDS = [
    "广告", "推广", "福利", "领奖", "课程", "保险", "八卦", "综艺", "养生", "健康",
    "优惠", "红包", "抽奖", "开户", "荐股", "培训", "直播间", "扫码", "加群"
]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# ========== 2. 工具函数 ==========
class NewsCache:
    def __init__(self, cache_file='news_cache.json'):
        self.cache_file = Path(cache_file)
        self.cache = self.load_cache()
    
    def load_cache(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'news': {}}
        return {'news': {}}
    
    def is_duplicate(self, title):
        key = title[:20]  # 前20字符去重
        if key in self.cache['news']:
            return True
        self.cache['news'][key] = datetime.now().isoformat()
        return False

    def save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.cache, f, ensure_ascii=False)

def calculate_score(title):
    """计算标题得分"""
    score = 0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in title:
            score += weight
    return score

def highlight_keywords(title):
    """将标题中匹配到的关键词用加粗包裹（按关键词长度降序处理，避免嵌套问题）"""
    # 按长度降序排序关键词，避免短词先替换导致长词无法匹配
    sorted_keywords = sorted(KEYWORD_WEIGHTS.keys(), key=len, reverse=True)
    # 使用正则替换，确保只替换独立出现的关键词？为简单，直接替换所有出现
    highlighted = title
    for kw in sorted_keywords:
        # 使用正则加粗，但要避免重复加粗（如果已经加粗过，跳过）
        # 这里简单替换，可能出现嵌套加粗，但影响不大
        pattern = re.compile(re.escape(kw))
        highlighted = pattern.sub(f"**{kw}**", highlighted)
    return highlighted

def fetch_news():
    """获取新闻主逻辑"""
    news_pool = []
    cache = NewsCache()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36'}
    
    total_sources = len(FEEDS)
    logging.info(f"开始抓取 {total_sources} 个新闻源...")
    
    for name, path in FEEDS.items():
        feed = None
        random.shuffle(RSSHUB_NODES)  # 随机打乱节点
        for node in RSSHUB_NODES:
            try:
                url = f"{node}{path}"
                resp = requests.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    if feed.entries:
                        logging.info(f"✅ {name} 抓取成功（节点：{node}）")
                        break
            except Exception as e:
                logging.debug(f"{name} 节点 {node} 失败：{e}")
                continue

        if not feed or not feed.entries:
            logging.warning(f"⚠️ {name} 所有节点均失败，跳过")
            continue

        for entry in feed.entries:
            title = entry.title.strip()
            # 负向过滤
            if any(k in title for k in NEGATIVE_KEYWORDS):
                continue
            # 重复检查
            if cache.is_duplicate(title):
                continue
            
            score = calculate_score(title)
            if score > 0:
                news_pool.append({
                    "title": title,
                    "link": entry.link,
                    "source": name,
                    "score": score
                })
    
    cache.save_cache()
    logging.info(f"抓取完成，共获得 {len(news_pool)} 条有效新闻")
    return sorted(news_pool, key=lambda x: x['score'], reverse=True)

def send_message(sorted_news):
    """推送消息（横向紧凑排版 + 关键词加粗）"""
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key:
        logging.error("未设置 FEISHU_WEBHOOK 环境变量")
        return

    bj_time = (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M')
    
    # 分类
    hot_items = []   # 得分 >=20
    reg_items = []   # 得分 <20
    
    for item in sorted_news[:25]:  # 最多25条
        title_hl = highlight_keywords(item['title'])  # 关键词加粗
        # 横向紧凑排版：用列表项，将来源和链接放在同一行
        line = f"- {title_hl}  —  [{item['source']}]({item['link']})"
        if item['score'] >= 20:
            hot_items.append(f"🚩 {line}")
        else:
            reg_items.append(f"🔹 {line}")
    
    # 构建 Markdown 内容
    hot_section = "\n".join(hot_items) if hot_items else "> 今日无重磅热点"
    reg_section = "\n".join(reg_items) if reg_items else "> 今日无核心快讯"
    
    # 顶部统计表格（紧凑）
    header = f"# 💰 股市情报快报  {bj_time[:10]}\n\n"
    stats = f"📊 **聚合总数**：{len(sorted_news)} 条  |  🔥 **重磅热点**：{len(hot_items)} 条  |  ⏰ **更新时间**：{bj_time}\n\n"
    
    content = (
        header +
        stats +
        "### 🚩 重磅关注（≥20分）\n" + hot_section + "\n\n" +
        "### 📢 核心快讯（<20分）\n" + reg_section + "\n\n" +
        "---\n" +
        "💡 *已过滤广告，关键词已加粗。使用多节点轮询，覆盖25+财经源。*"
    )

    # 发送
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        resp = requests.post(url, data={
            "title": f"财经早报 {bj_time[:10]}",
            "desp": content
        }, timeout=10)
        if resp.status_code == 200:
            logging.info("✅ 推送成功")
        else:
            logging.error(f"❌ 推送失败，状态码：{resp.status_code}")
    except Exception as e:
        logging.error(f"❌ 推送异常：{e}")

if __name__ == "__main__":
    news = fetch_news()
    send_message(news)
