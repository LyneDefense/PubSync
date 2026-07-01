"""赛道识别:从账号的 niche / tags / 品类 判断激活哪些行业规则包。

P1 只做**关键词映射**(零成本、覆盖头部);判不出就返回空(只走通用+平台包)。
P2 再加「便宜 LLM 兜底」把长尾归到固定枚举。一个号可命中多个赛道。
"""

from __future__ import annotations

# 赛道 → 触发关键词(出现在 niche/品类/tags/标题里任一即命中)。
_VERTICAL_KEYWORDS: dict[str, tuple[str, ...]] = {
    "cosmetics": ("护肤", "美妆", "彩妆", "化妆", "面膜", "精华", "口红", "美容", "护理", "美白", "抗老"),
    "medical": ("医疗", "医美", "健康", "养生", "医生", "护士", "口腔", "牙科", "皮肤科", "三甲", "科普医"),
    "food_health": ("保健", "食品", "零食", "营养", "代餐", "膳食", "滋补", "养生茶", "益生菌"),
    "maternal": ("母婴", "育儿", "奶粉", "辅食", "宝妈", "亲子", "孕", "婴儿", "儿童"),
    "finance": ("保险", "金融", "理财", "投资", "基金", "股票", "港险", "财富", "证券", "记账", "省钱攻略"),
    "education": ("教育", "考研", "考公", "雅思", "托福", "留学", "培训", "提分", "上岸", "公考", "四六级", "英语学习"),
    "fitness": ("减肥", "减脂", "健身", "瘦身", "塑形", "增肌", "瑜伽", "普拉提", "运动"),
    "recruit": ("招商", "加盟", "创业", "副业", "项目", "代理", "带你赚", "兼职"),
}


def detect_verticals(niche: str = "", tags: list[str] | None = None, titles: list[str] | None = None) -> list[str]:
    """返回命中的赛道 id 列表(可多个;判不出返回空)。

    niche/品类权重最高,tags 次之,标题兜底(标题只用前若干条,避免个别词误触发)。
    """
    hay_strong = " ".join([niche or "", " ".join(tags or [])])
    hay_weak = " ".join((titles or [])[:20])
    out: list[str] = []
    for vid, keywords in _VERTICAL_KEYWORDS.items():
        if any(k in hay_strong for k in keywords):
            out.append(vid)
        elif hay_weak and sum(1 for k in keywords if k in hay_weak) >= 2:
            # 标题里命中≥2个关键词才算(降低单标题误触发)
            out.append(vid)
    return out
