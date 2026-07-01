"""母婴规则包:婴配食品「母乳」宣称、母婴用品绝对化、焦虑营销。"""

from __future__ import annotations

from app.compliance.types import Confidence, Rule, RulePack, Severity

MATERNAL_PACK = RulePack(
    id="maternal",
    label="母婴",
    scope="vertical",
    activate_verticals=("maternal",),
    version="广告法 · 婴幼儿配方食品广告规",
    rules=(
        # 婴配食品「母乳/益智」宣称(certain,封号)
        Rule(
            id="infant_formula",
            category="母婴·婴配食品宣称",
            words=("接近母乳", "优于母乳", "替代母乳", "最接近母乳", "增强智力", "提高智力",
                   "益智", "增强抵抗力"),
            severity=Severity.BAN,
            confidence=Confidence.CERTAIN,
            basis="婴幼儿配方食品不得宣称接近/优于/替代母乳及益智",
            hint="删除母乳对比与益智宣称,只能客观描述成分",
        ),
        # 母婴用品绝对化(certain,限流)
        Rule(
            id="maternal_absolute",
            category="母婴·绝对化用语",
            words=("医用级", "灭菌级", "百分百无甲醛", "0甲醛", "防辐射", "无菌无毒"),
            severity=Severity.THROTTLE,
            confidence=Confidence.CERTAIN,
            basis="母婴用品禁用「医用级/灭菌/防辐射」等误导用语",
            hint="去掉「医用级/0甲醛/防辐射」,改成合规的材质说明",
        ),
        # 焦虑营销(weak → 提示)
        Rule(
            id="maternal_anxiety",
            category="母婴·焦虑营销",
            words=("输在起跑线", "再不管就晚了", "错过悔一生", "别人家孩子"),
            severity=Severity.NOTICE,
            confidence=Confidence.WEAK,
            basis="平台限制制造育儿焦虑的营销话术",
            hint="不要制造育儿焦虑,改成中性、支持性的表达",
        ),
    ),
)
