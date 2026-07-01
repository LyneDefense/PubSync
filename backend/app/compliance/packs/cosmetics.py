"""美妆护肤规则包。

核心纠偏:`美白/祛斑/祛痘` 是**合法的化妆品功效宣称**(特殊化妆品需注册,但可宣称),
不该判封号级——降为「提示级」友情提醒是否有资质。真正禁的是**医疗用语**(祛皱/抗菌/消炎/换肤)
和**绝对化功效**(一次见效/彻底根治)。
"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

COSMETICS_PACK = RulePack(
    id="cosmetics",
    label="美妆护肤",
    scope="vertical",
    activate_verticals=("cosmetics",),
    version="化妆品监督管理条例·功效宣称评价规范",
    rules=(
        # 医疗用语 / 药妆混淆:化妆品明令禁止(certain,封号)
        Rule(
            id="cosmetic_medical_word",
            category="化妆品·医疗用语",
            words=("祛皱", "去皱", "除皱", "抗菌", "抑菌", "除菌", "灭菌", "防菌", "杀菌",
                   "换肤", "祛疤", "去疤", "生发", "药妆", "医学护肤", "医美级"),
            allow_words=("抗皱", "减少皱纹", "预防皱纹", "淡化细纹"),  # 抗皱/减少皱纹 明确允许
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="化妆品不得使用医疗用语(祛皱/抗菌/消炎等明令禁止)",
            hint="改成允许的说法:皱纹→「抗皱/减少细纹」,菌→「清洁」,不要用医疗词",
        ),
        # 绝对化 / 速效功效:夸大(certain,限流)
        Rule(
            id="cosmetic_absolute",
            category="化妆品·夸大功效",
            words=("一次见效", "立刻美白", "立即美白", "7天变白", "彻底祛痘", "永久去黑头",
                   "根治痘痘", "药到病除", "包治痘痘"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="化妆品功效宣称评价规范·禁夸大速效",
            hint="去掉「一次见效/彻底/永久」,改成温和、可求证的体验表达",
        ),
        # 合法功效宣称,仅友情提示资质(weak → 提示级,不算违规)
        Rule(
            id="cosmetic_functional",
            category="化妆品·功效宣称(需资质)",
            words=("美白", "祛斑", "淡斑", "祛痘", "淡纹", "抗衰老", "抗初老", "修复受损",
                   "淡化痘印", "去黑头", "紧致"),
            severity=Severity.NOTICE,
            confidence=Confidence.WEAK,
            basis="美白/祛斑属特殊化妆品功效,产品需注册备案后方可宣称",
            hint="确认产品已注册对应功效即可正常表达;否则弱化为使用体验",
        ),
    ),
)
