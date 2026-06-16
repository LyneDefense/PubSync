"""平台限流/违禁词的内置词库(自行整理的事实性词表,按类别维护)。

分通用类(三平台共用)+ 平台特定类。build_blocklist(platform) 合并成「类别→词」与扁平反查表。
词库故意从精炼的高频词起步,覆盖大多数踩坑场景;可经 AppSetting(compliance_extra_words)再扩展。
"""

from __future__ import annotations

# 极限词 / 绝对化用语(广告法重灾区,踩中有罚款+限流双重风险)。
# 注:故意只收较无歧义的「营销超级词」,不收会误伤日常用语的裸字(如 最/第一/完全/彻底)。
COMMON_EXTREME = [
    "最佳", "最好", "最强", "最优", "最低价", "最高级", "最便宜", "最受欢迎", "最先进",
    "全网第一", "销量第一", "排名第一", "中国第一", "全国第一", "世界第一", "宇宙第一",
    "独一无二", "绝无仅有", "前无古人", "史无前例",
    "顶级", "极致", "极品", "国家级", "世界级", "世界领先",
    "首家", "独家", "领袖品牌", "百分百", "万能",
]

# 医疗/功效宣称(小红书等尤其严)。
COMMON_MEDICAL = [
    "治愈", "治疗", "疗效", "根治", "痊愈", "药用", "处方",
    "消炎", "抗炎", "抗菌", "杀菌", "灭菌", "除菌", "消毒",
    "减肥", "瘦身", "燃脂", "排毒", "祛湿", "清热解毒", "滋阴", "壮阳", "补肾",
    "助眠", "失眠", "抗衰老", "祛斑", "祛痘", "美白", "修复受损", "提高免疫力", "增强免疫力", "调节内分泌",
    "防癌", "抗癌", "降血压", "降血糖", "丰胸",
]

# 诱导互动 / 营销过度(直白导流、抽奖、抢购话术)。
COMMON_INDUCEMENT = [
    "加微信", "加微", "扫码", "扫二维码", "加群", "加我",
    "点击购买", "点击链接", "点击下方", "点我", "戳链接", "下单链接", "购买链接",
    "秒杀", "抢爆", "疯抢", "万人疯抢", "限时抢购", "不会再便宜", "错过不再", "清仓", "甩卖",
    "恭喜获奖", "全民免单", "免费领取", "免费送", "点击有惊喜", "0元购", "白嫖",
    "返现", "返利", "刷单", "代购", "微商",
]

# 基线兜底:政治敏感/色情/暴力/违法(模型一般会避,这里仅极少量关键词兜底,避免误伤)。
COMMON_BASELINE = [
    "赌博", "博彩", "毒品", "走私", "诈骗", "传销", "枪支", "fa轮", "色情", "裸聊", "约炮",
]

# 平台特定:竞品代称 / 外链平台名等。
PLATFORM_EXTRA: dict[str, list[str]] = {
    "xhs": ["淘宝", "天猫", "京东", "拼多多", "抖音", "快手", "微信", "公众号", "TikTok", "tb", "v信"],
    "douyin": ["淘宝", "天猫", "京东", "拼多多", "小红书", "微信", "公众号", "快手", "B站", "微信号"],
    "wechat": ["抖音", "小红书", "淘宝", "拼多多"],
}

# 类别 → 通俗改写建议(给模型/用户看,不带术语)。
CATEGORY_HINTS: dict[str, str] = {
    "极限词": "去掉绝对化说法,改成客观描述(例:把“最好用”改成“我用下来比较顺手”)",
    "医疗功效": "不要宣称疗效,改成温和、可求证的表达(例:把“治愈痘痘”改成“用着感觉皮肤舒服一些”)",
    "诱导营销": "去掉直白导流和抢购话术,改成自然的分享和轻量互动",
    "竞品外链": "不要直接点名其他平台或带外链,换成不具体指向的说法",
    "基线": "移除该违规内容",
}

# 类别常量(与 build_blocklist 的键一致)。
CATEGORY_EXTREME = "极限词"
CATEGORY_MEDICAL = "医疗功效"
CATEGORY_INDUCEMENT = "诱导营销"
CATEGORY_BASELINE = "基线"
CATEGORY_PLATFORM = "竞品外链"


def build_blocklist(platform: str) -> dict[str, list[str]]:
    """返回该平台的「类别 → 词列表」(通用类 + 平台特定类)。"""
    return {
        CATEGORY_EXTREME: list(COMMON_EXTREME),
        CATEGORY_MEDICAL: list(COMMON_MEDICAL),
        CATEGORY_INDUCEMENT: list(COMMON_INDUCEMENT),
        CATEGORY_BASELINE: list(COMMON_BASELINE),
        CATEGORY_PLATFORM: list(PLATFORM_EXTRA.get(platform, [])),
    }


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
