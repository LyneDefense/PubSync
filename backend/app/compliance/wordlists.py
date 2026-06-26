"""平台限流/违禁词的内置词库(自行整理的事实性词表),带分级 + 官方依据 + 品类红线。

每个类别有:词列表 + 分级(封号级/限流级/提示级)+ 官方依据 + 通俗改写建议。
build_blocklist(platform, industry) 合并通用类 + 平台特定类 +(按品类)红线类。
词库从精炼高频词起步,覆盖大多数踩坑场景;可经 AppSetting(compliance_extra_words)再扩展。
"""

from __future__ import annotations

# —— 分级 ——
SEVERITY_BAN = "封号级"  # 导流/保证收益/医疗功效/敏感违禁:轻则下架限流,重则封号
SEVERITY_THROTTLE = "限流级"  # 极限词/夸大/抢购:笔记限流、文案被屏蔽
SEVERITY_NOTICE = "提示级"  # 边界/轻微:提示优化


# 极限词 / 绝对化用语(广告法重灾区)。只收较无歧义的「营销超级词」,不收会误伤日常用语的裸字。
COMMON_EXTREME = [
    "最佳", "最好", "最强", "最优", "最低价", "最高级", "最便宜", "最受欢迎", "最先进",
    "全网第一", "销量第一", "排名第一", "中国第一", "全国第一", "世界第一", "宇宙第一",
    "独一无二", "绝无仅有", "前无古人", "史无前例",
    "顶级", "极致", "极品", "国家级", "世界级", "世界领先",
    "首家", "独家", "领袖品牌", "百分百", "万能",
]

# 保证 / 承诺类(绝对保证误导消费者)。
COMMON_GUARANTEE = [
    "保证有效", "保证治愈", "无效退款", "100%有效", "百分百有效", "绝对安全", "绝对有效",
    "永久有效", "永不复发", "包好", "包治", "包过", "零风险", "无任何副作用",
]

# 导流 / 私域引流(严禁导流站外，《交易导流商业秩序治理规则》)。
COMMON_DIVERSION = [
    "加微信", "加微", "加我微信", "扫码", "扫二维码", "加群", "加我", "私信领取", "私我",
    "vx", "v信", "薇信", "威信", "微信号", "公众号", "外链", "链接见主页", "主页领取",
    "点击购买", "点击链接", "点击下方", "戳链接", "下单链接", "购买链接",
]

# 诱导互动 / 抢购抽奖(过度营销话术)。
COMMON_INDUCEMENT = [
    "秒杀", "抢爆", "疯抢", "万人疯抢", "限时抢购", "不会再便宜", "错过不再", "清仓", "甩卖",
    "恭喜获奖", "全民免单", "免费领取", "免费送", "点击有惊喜", "0元购", "白嫖",
    "返现", "返利", "刷单", "代购", "微商",
]

# 医疗/功效宣称(小红书等尤其严;医美/三品一械红线)。
COMMON_MEDICAL = [
    "治愈", "治疗", "疗效", "根治", "痊愈", "药用", "处方",
    "消炎", "抗炎", "抗菌", "杀菌", "灭菌", "除菌", "消毒",
    "减肥", "瘦身", "燃脂", "排毒", "祛湿", "清热解毒", "滋阴", "壮阳", "补肾",
    "助眠", "失眠", "抗衰老", "祛斑", "祛痘", "美白", "修复受损", "提高免疫力", "增强免疫力", "调节内分泌",
    "防癌", "抗癌", "降血压", "降血糖", "丰胸",
]

# 基线兜底:政治敏感/色情/暴力/违法。
COMMON_BASELINE = [
    "赌博", "博彩", "毒品", "走私", "诈骗", "传销", "枪支", "fa轮", "色情", "裸聊", "约炮",
]

# 平台特定:竞品代称 / 外链平台名。
PLATFORM_EXTRA: dict[str, list[str]] = {
    "xhs": ["淘宝", "天猫", "京东", "拼多多", "抖音", "快手", "TikTok", "tb"],
    "douyin": ["淘宝", "天猫", "京东", "拼多多", "小红书", "快手", "B站"],
    "wechat": ["抖音", "小红书", "淘宝", "拼多多"],
}

# —— 品类红线词(按品类挂,只在诊断/扫描该品类时启用)——
# 金融/保险/理财:无资质禁「具体收益承诺/保本保收益」。
FINANCE_GUARANTEE = [
    "保本", "保收益", "稳赚", "稳赚不赔", "稳赔", "包赚", "躺赚", "刚兑", "保息", "保底收益",
    "承诺收益", "承诺年化", "零风险投资", "无风险", "百分百回本", "翻倍收益", "高额返利",
]

# 类别常量(与 build_blocklist 的键一致)。
CATEGORY_EXTREME = "极限词"
CATEGORY_GUARANTEE = "保证承诺"
CATEGORY_DIVERSION = "导流"
CATEGORY_INDUCEMENT = "诱导营销"
CATEGORY_MEDICAL = "医疗功效"
CATEGORY_BASELINE = "敏感违禁"
CATEGORY_PLATFORM = "竞品外链"
CATEGORY_FINANCE = "金融保险·保证收益"

# 类别 → 元数据:词、分级、官方依据、通俗改写建议。
_META: dict[str, dict] = {
    CATEGORY_EXTREME: {"words": COMMON_EXTREME, "severity": SEVERITY_THROTTLE, "basis": "广告法绝对化用语",
                       "hint": "去掉绝对化说法,改成客观描述(把“最好用”改成“我用下来比较顺手”)"},
    CATEGORY_GUARANTEE: {"words": COMMON_GUARANTEE, "severity": SEVERITY_THROTTLE, "basis": "广告法+营销治理",
                         "hint": "不要做绝对保证/承诺,改成“多数人反馈”“因人而异”"},
    CATEGORY_DIVERSION: {"words": COMMON_DIVERSION, "severity": SEVERITY_BAN, "basis": "交易导流商业秩序治理规则",
                         "hint": "不要留联系方式/外链/引导私域,改成站内自然互动"},
    CATEGORY_INDUCEMENT: {"words": COMMON_INDUCEMENT, "severity": SEVERITY_THROTTLE, "basis": "营销违规词",
                          "hint": "去掉抢购/抽奖话术,改成自然分享和轻量互动"},
    CATEGORY_MEDICAL: {"words": COMMON_MEDICAL, "severity": SEVERITY_BAN, "basis": "医疗/医美/三品一械红线",
                       "hint": "不要宣称疗效,改成温和、可求证的体验表达"},
    CATEGORY_BASELINE: {"words": COMMON_BASELINE, "severity": SEVERITY_BAN, "basis": "社区规范",
                        "hint": "移除该违规内容"},
    CATEGORY_PLATFORM: {"words": [], "severity": SEVERITY_THROTTLE, "basis": "导流治理/平台规则",
                        "hint": "不要点名其他平台或带外链,换成不具体指向的说法"},
    CATEGORY_FINANCE: {"words": FINANCE_GUARANTEE, "severity": SEVERITY_BAN, "basis": "金融保险品类红线(无资质禁收益承诺)",
                       "hint": "不要承诺收益/保本,改成风险提示和客观说明,投资建议需持牌"},
}

# 品类 → 启用的红线类别(关键词命中其中之一即认定该品类)。
INDUSTRY_RULES: dict[str, list[str]] = {
    "保险": [CATEGORY_FINANCE],
    "金融": [CATEGORY_FINANCE],
    "理财": [CATEGORY_FINANCE],
    "投资": [CATEGORY_FINANCE],
    "基金": [CATEGORY_FINANCE],
    "股票": [CATEGORY_FINANCE],
}

# 向后兼容:旧代码引用的 CATEGORY_HINTS（类别→改写建议）。
CATEGORY_HINTS: dict[str, str] = {cat: meta["hint"] for cat, meta in _META.items()}


def category_severity(category: str) -> str:
    return _META.get(category, {}).get("severity", SEVERITY_NOTICE)


def category_basis(category: str) -> str:
    return _META.get(category, {}).get("basis", "")


def resolve_industry(industry: str | None) -> list[str]:
    """把品类(可能是“香港保险”这类长词)解析成启用的红线类别。模糊包含匹配。"""
    if not industry:
        return []
    text = industry.strip()
    cats: list[str] = []
    for key, categories in INDUSTRY_RULES.items():
        if key in text:
            for c in categories:
                if c not in cats:
                    cats.append(c)
    return cats


def build_blocklist(platform: str, industry: str | None = None) -> dict[str, list[str]]:
    """返回该平台的「类别 → 词列表」(通用类 + 平台竞品类 +(按品类)红线类)。"""
    blocklist: dict[str, list[str]] = {
        CATEGORY_EXTREME: list(COMMON_EXTREME),
        CATEGORY_GUARANTEE: list(COMMON_GUARANTEE),
        CATEGORY_DIVERSION: list(COMMON_DIVERSION),
        CATEGORY_INDUCEMENT: list(COMMON_INDUCEMENT),
        CATEGORY_MEDICAL: list(COMMON_MEDICAL),
        CATEGORY_BASELINE: list(COMMON_BASELINE),
        CATEGORY_PLATFORM: list(PLATFORM_EXTRA.get(platform, [])),
    }
    for cat in resolve_industry(industry):
        blocklist[cat] = list(_META.get(cat, {}).get("words", []))
    return blocklist


def flatten_blocklist(blocklist: dict[str, list[str]]) -> dict[str, str]:
    """词 → 类别 的扁平反查表(同词多类时,先出现的类别优先)。"""
    word_to_category: dict[str, str] = {}
    for category, words in blocklist.items():
        for word in words:
            word_to_category.setdefault(word, category)
    return word_to_category


def prompt_guidance(platform: str, examples_per_category: int = 4) -> str:
    """给提示词用的「限流词规避」精简说明:每类几个例词 + 通俗改写策略(不 dump 全表)。"""
    blocklist = build_blocklist(platform)
    lines: list[str] = []
    for category, words in blocklist.items():
        if not words:
            continue
        sample = "、".join(words[:examples_per_category])
        hint = CATEGORY_HINTS.get(category, "")
        lines.append(f"- {category}(如 {sample} 等):{hint}")
    return "\n".join(lines)
