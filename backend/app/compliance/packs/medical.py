"""医疗健康规则包:疗效宣称 / 疾病治疗 / 三品一械。

疗效、疾病治疗是硬红线(certain,封号)。三品一械/医美「提到 vs 推荐」有别——
P1 先按 weak 提示(避免误伤科普),推荐/售卖意图留给 P2 的 LLM 裁判。
"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

MEDICAL_PACK = RulePack(
    id="medical",
    label="医疗健康",
    scope="vertical",
    activate_verticals=("medical",),
    version="广告法16-19条 · 2026-02 三品一械禁推令",
    rules=(
        # 疾病治疗宣称——医疗健康赛道更细的红线(通用「疗效宣称」在 common 里已覆盖 治愈/根治/抗癌 等)
        Rule(
            id="medical_disease",
            category="医疗·疾病治疗",
            words=("治疗", "降三高", "治糖尿病", "治高血压", "补肾", "治失眠", "治便秘",
                   "调理三高", "改善视力", "治疗近视"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="广告法·不得涉及疾病治疗功能",
            hint="删除疾病治疗宣称,健康类内容不得暗示治病",
        ),
        # 三品一械 / 医美:提到即需谨慎(weak → 提示,推荐/售卖交 LLM 判)
        Rule(
            id="medical_aesthetic",
            category="医美·三品一械",
            words=("水光针", "热玛吉", "玻尿酸注射", "肉毒素", "瘦脸针", "线雕", "超声刀",
                   "埋线", "医美项目", "医疗器械", "处方药"),
            severity=Severity.THROTTLE,
            confidence=Confidence.WEAK,
            basis="2026-02 三品一械禁推令·禁推荐/售卖",
            hint="平台已禁推荐/售卖三品一械与医美项目,科普也需去除引导消费的表述",
        ),
    ),
)
