import feedparser
import requests
import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

# ========== 配置区 ==========
RSSHUB_BASE = "https://rss-hub-nu-one.vercel.app" 

# 新闻源配置
FEEDS = {
    "🔥 财新网财经": f"{RSSHUB_BASE}/caixin/finance/charge",
    "📢 第一财经热点": f"{RSSHUB_BASE}/yicai/brief",
    "📊 界面新闻证券": f"{RSSHUB_BASE}/jiemian/v4/news/22",
    "⚡ 36氪快讯": f"{RSSHUB_BASE}/36kr/newsflashes",
    "🏙️ 澎湃财经": f"{RSSHUB_BASE}/thepaper/channel/25951",
    "📈 经观股市": f"{RSSHUB_BASE}/eeo/category/11",
    "💰 21世纪经济": f"{RSSHUB_BASE}/21jingji/channel/investment"
}

# ========== 关键词权重配置 ==========

# 🚨 紧急重磅词 (权重25分)
URGENT_KEYWORDS = [
    "紧急", "突发", "重磅", "快讯", "最新", 
    "刚刚", "央行", "证监会", "银保监会", "国务院",
    "政治局", "中央", "白宫", "美联储", "欧央行"
]

# 💰 政策宏观词 (权重20分)
POLICY_KEYWORDS = [
    "降息", "加息", "降准", "MLF", "LPR", "逆回购",
    "货币政策", "财政政策", "利率", "准备金率",
    "CPI", "PPI", "PMI", "GDP", "经济数据",
    "放水", "收紧", "宽松", "紧缩"
]

# 📈 市场热点词 (权重15分)
MARKET_KEYWORDS = [
    "A股", "港股", "美股", "股票", "证券", "股市",
    "大盘", "指数", "上证", "深证", "创业板",
    "科创", "北向资金", "主力资金", "成交量",
    "涨停", "跌停", "破发", "新高", "新低",
    "牛市", "熊市", "反弹", "回调"
]

# 🏢 公司动态词 (权重15分)
COMPANY_KEYWORDS = [
    # 科技互联网
    "腾讯", "阿里", "美团", "京东", "拼多多",
    "百度", "字节", "抖音", "快手", "小米",
    "华为", "中兴", "网易", "微博", "B站",
    # 金融
    "茅台", "五粮液", "平安", "招商银行", "中信",
    "高盛", "摩根", "黑石", "桥水", "贝莱德",
    # 新能源车
    "特斯拉", "比亚迪", "蔚来", "小鹏", "理想",
    # 芯片科技
    "英伟达", "AMD", "英特尔", "台积电", "三星",
    "中芯国际", "寒武纪", "海光"
]

# 📊 业绩财报词 (权重12分)
EARNINGS_KEYWORDS = [
    "财报", "业绩", "营收", "净利润", "毛利率",
    "每股收益", "EPS", "ROE", "净资产收益率",
    "同比增长", "环比增长", "扭亏", "预增",
    "预减", "预亏", "预警", "修正"
]

# 🔄 交易并购词 (权重12分)
DEAL_KEYWORDS = [
    "收购", "并购", "重组", "借壳", "IPO",
    "上市", "定增", "增发", "配股", "可转债",
    "减持", "增持", "回购", "股权激励",
    "战略投资", "融资", "募资"
]

# 📉 风险预警词 (权重10分)
RISK_KEYWORDS = [
    "暴跌", "暴涨", "崩盘", "熔断", "退市",
    "做空", "唱空", "利空", "利好",
    "风险", "预警", "警示", "立案", "调查",
    "处罚", "罚款", "违约", "暴雷"
]

# 🏭 行业产业词 (权重8分)
INDUSTRY_KEYWORDS = [
    "新能源", "光伏", "风电", "锂电", "储能",
    "芯片", "半导体", "AI", "人工智能", "数字经济",
    "消费", "医药", "医疗", "房地产", "基建",
    "外贸", "出口", "进口", "关税", "贸易"
]

# ========== 负向过滤词 ==========
NEGATIVE_KEYWORDS = [
    # 广告推广
    "广告", "推广", "营销", "促销", "特惠",
    "优惠", "福利", "红包", "领奖", "抽奖",
    "开户", "入金", "荐股", "课程", "培训",
    "直播间", "扫码", "加群", "私聊", "助理",
    # 低质内容
    "养生", "健康", "情感", "鸡汤", "娱乐",
    "八卦", "明星", "影视", "综艺", "游戏",
    # 保险理财
    "保险", "理财", "定投", "基金定投",
    "年金", "寿险", "重疾险", "医疗险",
    # 推广套路
    "限时", "最后一天", "错过", "后悔",
    "暴涨", "秘籍", "揭秘", "内幕", "绝密"
]

# ========== 关键词权重映射 ==========
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

# ========== 日志配置 ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# ========== 新闻缓存类 ==========
class NewsCache:
    """新闻缓存，避免重复推送"""
    def __init__(self, cache_file='news_cache.json', expire_hours=24):
        self.cache_file = Path(cache_file)
        self.expire_hours = expire_hours
        self.cache = self.load_cache()
    
    def load_cache(self):
        """加载缓存文件"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {'news': {}, 'last_cleanup': datetime.now().isoformat()}
        return {'news': {}, 'last_cleanup': datetime.now().isoformat()}
    
    def is_duplicate(self, title, source):
        """检查是否重复新闻"""
        # 简单去重：用标题前20个字符作为key
        key = title[:20]
        
        if key in self.cache['news']:
            return True
        
        # 添加新新闻
        self.cache['news'][key] = {
            'timestamp': datetime.now().isoformat(),
            'source': source,
            'title': title
        }
        return False
    
    def cleanup_expired(self):
        """清理过期缓存"""
        now = datetime.now()
        expired = []
        
        for key, data in self.cache['news'].items():
            try:
                timestamp = datetime.fromisoformat(data['timestamp'])
                if (now - timestamp) > timedelta(hours=self.expire_hours):
                    expired.append(key)
            except:
                expired.append(key)
        
        for key in expired:
            del self.cache['news'][key]
        
        self.cache['last_cleanup'] = now.isoformat()
        self.save_cache()
        logging.info(f"缓存清理完成，移除 {len(expired)} 条过期记录")
    
    def save_cache(self):
        """保存缓存到文件"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"保存缓存失败: {e}")

# ========== 工具函数 ==========
def calculate_score(title):
    """
    计算新闻标题的综合得分
    """
    score = 0
    matched_keywords = []
    
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in title:
            score += weight
            matched_keywords.append(keyword)
    
    # 去重加分：如果匹配到多个不同类别，额外加分
    unique_keywords = set(matched_keywords)
    if len(unique_keywords) >= 3:
        score += 10
    elif len(unique_keywords) >= 2:
        score += 5
    
    # 标题长度奖励/惩罚
    if len(title) < 8:
        score -= 5
    elif len(title) > 30:
        score += 3
        
    return max(0, score)

def find_top_keywords(title, top_n=3):
    """找出标题中权重最高的关键词"""
    matches = []
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in title:
            matches.append((keyword, weight))
    
    matches.sort(key=lambda x: x[1], reverse=True)
    return [k for k, w in matches[:top_n]]

def get_beijing_time():
    """获取北京时间"""
    return (datetime.utcnow() + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')

# ========== 核心功能函数 ==========
def fetch_news():
    """
    获取并筛选新闻
    """
    news_pool = []
    cache = NewsCache()
    
    logging.info("开始获取新闻...")
    
    for name, url in FEEDS.items():
        try:
            logging.info(f"正在获取: {name}")
            feed = feedparser.parse(url)
            
            # 检查是否获取成功
            if hasattr(feed, 'status') and feed.status != 200:
                logging.warning(f"{name} 返回状态码: {feed.status}")
                continue
            
            entry_count = 0
            for entry in feed.entries:
                title = entry.title.strip()
                
                # 负向关键词过滤
                if any(k in title for k in NEGATIVE_KEYWORDS):
                    continue
                
                # 重复检查
                if cache.is_duplicate(title, name):
                    continue
                
                # 计算得分
                score = calculate_score(title)
                
                # 只保留有相关性的新闻（得分>0）
                if score > 0:
                    news_pool.append({
                        "title": title,
                        "link": entry.link,
                        "source": name,
                        "score": score,
                        "published": entry.get('published', '未知时间')
                    })
                    entry_count += 1
            
            logging.info(f"{name} 获取到 {entry_count} 条有效新闻")
            
        except Exception as e:
            logging.error(f"获取 {name} 失败: {e}")
            continue
    
    # 清理缓存
    cache.cleanup_expired()
    
    # 合并重复标题（不同源）
    unique_news = {}
    for item in news_pool:
        title = item['title']
        if title not in unique_news:
            unique_news[title] = item
        else:
            unique_news[title]['score'] += 5
            unique_news[title]['source'] += f"、{item['source']}"
    
    # 按得分排序
    sorted_news = sorted(unique_news.values(), key=lambda x: x['score'], reverse=True)
    
    logging.info(f"新闻聚合完成，共 {len(sorted_news)} 条有效新闻")
    return sorted_news[:30]  # 只返回前30条

def send_message(sorted_news):
    """
    推送消息到Server酱
    """
    send_key = os.environ.get('FEISHU_WEBHOOK')
    if not send_key:
        logging.error("❌ 未读取到 FEISHU_WEBHOOK 环境变量")
        return

    bj_time = get_beijing_time()
    
    # 分类新闻
    hot_items = []
    regular_items = []
    
    for item in sorted_news[:20]:  # 最多推送20条
        # 获取匹配的关键词
        top_keywords = find_top_keywords(item['title'])
        keyword_tag = f" `{', '.join(top_keywords)}`" if top_keywords else ""
        
        # 格式化条目
        formatted_entry = (
            f"## {item['title']}\n"
            f"> {item['source']}{keyword_tag} | [查看原文]({item['link']})\n"
            f"---"
        )
        
        if item['score'] >= 20:
            hot_items.append(f"🚩 {formatted_entry}")
        else:
            regular_items.append(f"🔹 {formatted_entry}")

    # 组装消息
    if not sorted_news:
        content = f"# 💰 股市早报 | {bj_time}\n\n> 今日暂无符合条件的重点资讯。"
    else:
        # 统计信息
        total_score = sum(item['score'] for item in sorted_news)
        avg_score = total_score / len(sorted_news)
        
        stat_header = (
            f"| 统计维度 | 数据 |\n"
            f"| :--- | :--- |\n"
            f"| 📊 聚合总数 | {len(sorted_news)} 条 |\n"
            f"| 🔥 重磅热点 | {len(hot_items)} 条 |\n"
            f"| 📈 平均热度 | {avg_score:.1f} 分 |\n"
            f"| ⏰ 更新时间 | {bj_time} |\n\n"
        )
        
        hot_section = (
            f"### 🚩 重磅热点（{len(hot_items)}条）\n"
            f"{chr(10).join(hot_items) if hot_items else '> 暂无超高热度资讯'}\n\n"
        )
        
        regular_section = (
            f"### 📢 市场核心（{len(regular_items)}条）\n"
            f"{chr(10).join(regular_items) if regular_items else '> 暂无相关资讯'}\n\n"
        )
        
        content = (
            f"# 💰 股市情报快报\n\n"
            f"{stat_header}"
            f"{hot_section}"
            f"{regular_section}"
            f"---\n"
            f"💡 *已自动过滤广告推广，保留核心市场动态*\n"
            f"📊 *热度评分：≥20分🔥重磅 | <20分📢核心*"
        )

    # 发送到Server酱
    url = f"https://sctapi.ftqq.com/{send_key}.send"
    try:
        response = requests.post(
            url, 
            data={
                "title": f"财经早报 {bj_time[:10]}",
                "desp": content
            },
            timeout=10
        )
        
        if response.status_code == 200:
            logging.info(f"✅ 推送成功，共 {len(sorted_news)} 条新闻")
        else:
            logging.error(f"❌ 推送失败: {response.status_code}")
            
    except Exception as e:
        logging.error(f"❌ 推送异常: {e}")

# ========== 主函数 ==========
def main():
    """
    主函数
    """
    logging.info("=" * 50)
    logging.info("财经新闻聚合推送服务启动")
    logging.info("=" * 50)
    
    try:
        # 获取新闻
        final_news = fetch_news()
        
        # 推送消息
        send_message(final_news)
        
        # 输出统计信息
        if final_news:
            logging.info(f"最高分新闻: {final_news[0]['title']} (得分: {final_news[0]['score']})")
        
        logging.info("=" * 50)
        logging.info("本次运行完成")
        logging.info("=" * 50)
        
    except Exception as e:
        logging.error(f"程序运行出错: {e}")
        raise

if __name__ == "__main__":
    main()
