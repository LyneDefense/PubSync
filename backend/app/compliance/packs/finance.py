"""金融保险规则包(迁移自旧 FINANCE_GUARANTEE):无资质禁收益承诺 / 荐股。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

FINANCE_PACK = RulePack(
    id="finance",
    label="金融保险",
    scope="vertical",
    activate_verticals=("finance",),
    version="资管新规 · 广告法·金融红线",
    rules=(
        # 保本 / 保收益(certain,封号)
        Rule(
            id="finance_guarantee",
            category="金融·保证收益",
            words=("保本", "保收益", "稳赚", "稳赚不赔", "包赚", "躺赚", "刚兑", "保息",
                   "保底收益", "承诺收益", "承诺年化", "零风险投资", "无风险", "百分百回本",
                   "翻倍收益", "保本保息", "稳赔"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="金融保险品类红线(无资质禁收益承诺/保本)",
            hint="不要承诺收益/保本,改成风险提示和客观说明,投资建议需持牌",
        ),
        # 荐股 / 具体投资建议(weak → 提示,无资质越界交 LLM 判)
        Rule(
            id="finance_advice",
            category="金融·荐股建议",
            words=("满仓", "梭哈", "抄底", "牛股", "涨停板", "内幕消息", "推荐买入", "闭眼买"),
            severity=Severity.THROTTLE,
            confidence=Confidence.WEAK,
            basis="无证券投顾资质不得给具体买卖建议",
            hint="不要给具体买卖点/荐股,改成方法论与风险提示",
        ),
    ),
)
