"""招商加盟规则包:暴利话术 / 传销拉人头。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

RECRUIT_PACK = RulePack(
    id="recruit",
    label="招商加盟",
    scope="vertical",
    activate_verticals=("recruit",),
    version="反不正当竞争 · 禁止传销条例",
    rules=(
        # 传销特征(certain,封号)
        Rule(
            id="recruit_pyramid",
            category="招商·传销特征",
            words=("拉人头", "发展下线", "交入门费", "拉下线", "人头费", "多层返利"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="禁止传销条例",
            hint="删除拉人头/发展下线等传销话术",
        ),
        # 暴利承诺(certain,限流)
        Rule(
            id="recruit_profit",
            category="招商·暴利承诺",
            words=("日入过万", "月入十万", "轻松月入", "一夜暴富", "暴利", "包回本",
                   "零风险创业", "躺着赚钱", "财富自由", "稳赚不赔"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="广告法·禁夸大收益承诺",
            hint="去掉「日入过万/暴利/包回本」,改成真实、可核验的说明",
        ),
    ),
)
