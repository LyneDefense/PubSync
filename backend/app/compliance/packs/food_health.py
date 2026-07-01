"""食品 / 保健品规则包:保健食品不得宣疗效;食品「零添加」新规。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

FOOD_HEALTH_PACK = RulePack(
    id="food_health",
    label="食品保健",
    scope="vertical",
    activate_verticals=("food_health",),
    version="保健食品广告审查办法 · 食品标识新规",
    rules=(
        # 保健食品/食品宣疗效或保健功效越界(certain,封号)
        Rule(
            id="health_food_effect",
            category="食品·功效越界",
            words=("增强免疫力", "提高免疫力", "调节内分泌", "排毒", "祛湿", "清热解毒",
                   "滋阴", "降血脂", "调节三高", "养胃护肝", "补气血"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="保健食品不得宣称疾病预防/治疗;食品不得宣保健功效",
            hint="删除功效/疗效宣称,普通食品只能描述口感/成分,保健食品须用批准的功能表述",
        ),
        # 「零添加」类:2026 食品标识新规限制(weak → 提示)
        Rule(
            id="zero_additive",
            category="食品·零添加宣称",
            words=("零添加", "无添加", "纯天然", "不含防腐剂", "0添加"),
            severity=Severity.NOTICE,
            confidence=Confidence.WEAK,
            basis="食品标识新规·限制「零添加」等宣称",
            hint="「零添加」将受限,改成客观描述配料表",
        ),
    ),
)
