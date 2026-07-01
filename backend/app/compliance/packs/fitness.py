"""减肥健身规则包:禁快速瘦身夸大功效。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

FITNESS_PACK = RulePack(
    id="fitness",
    label="减肥健身",
    scope="vertical",
    activate_verticals=("fitness",),
    version="广告法·虚假宣传",
    rules=(
        # 快速瘦身夸大(certain,限流)
        Rule(
            id="fitness_rapid",
            category="减肥·快速瘦身夸大",
            words=("暴瘦", "躺瘦", "月瘦", "周瘦", "7天瘦", "一周瘦", "狂瘦", "喝水都瘦",
                   "不反弹", "睡觉瘦", "怎么吃都不胖"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="广告法·禁夸大快速减重效果",
            hint="去掉「暴瘦/躺瘦/不反弹」,改成科学、循序渐进的表达",
        ),
        # 燃脂类常见词(weak → 提示)
        Rule(
            id="fitness_soft",
            category="减肥·功效用语",
            words=("燃脂", "甩脂", "刷脂", "掉秤", "爆汗掉秤"),
            severity=Severity.NOTICE,
            confidence=Confidence.WEAK,
            basis="减脂功效需客观,避免夸大",
            hint="弱化「燃脂/甩脂」等确定性功效词,改成运动/饮食方法",
        ),
    ),
)
