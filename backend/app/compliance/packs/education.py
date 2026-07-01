"""教育培训规则包:禁升学/通过考试的保证性承诺。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

EDUCATION_PACK = RulePack(
    id="education",
    label="教育培训",
    scope="vertical",
    activate_verticals=("education",),
    version="广告法第24条",
    rules=(
        Rule(
            id="education_guarantee",
            category="教育·保证性承诺",
            words=("保过", "包过", "保录取", "保证提分", "一次通过", "不过退款", "保上岸",
                   "包上岸", "保offer", "保签约", "100%通过", "保重点"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="广告法第24条·禁对升学/通过考试作保证性承诺",
            hint="删除「保过/保上岸/包录取」等承诺,改成课程内容与过往情况客观说明",
        ),
    ),
)
