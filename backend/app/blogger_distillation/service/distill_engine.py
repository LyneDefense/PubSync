"""博主蒸馏 LLM 引擎(车道化):内核(认知/策略/人设)+ 按模态车道的内容层,各自用合成循环包裹。

- **内核**吃「全部笔记」(含 unknown 视频):认知层/策略层/人设——人的层面,跨模态一致。
- **每条内容车道**只吃该 `content_subtype` 的笔记:内容层——表达的层面,图文/口播/非口播写法不同。

被编排层 :mod:`.distillation` 调用:``distill_core`` 一次 + ``distill_lane`` 对每条 present 车道各一次。
本模块不碰 DB、不写任务事件。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.blogger_distillation.evidence import render_grounding, render_stats_digest
from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    VIDEO,
    subtype_label,
)
from app.config import Settings
from app.models import BloggerProfile
from app.blogger_distillation.schema import CoreDistillation, LaneContent
from app.prompts import anti_injection, output_schema, prompt, render_schema
from app.services.ai_service import AIServiceError, create_json_response
from app.synthesis import (
    Critic,
    SensorResult,
    SynthesisBudget,
    SynthesisTrace,
    TaskGuide,
    run_synthesis,
)


def normalize_mode(mode: str | None) -> str:
    """A=拆解对标博主（默认）；B=诊断我的账号。其它一律按 A 处理。"""
    return "B" if str(mode or "").strip().upper() == "B" else "A"


@dataclass
class DistillContext:
    """一次蒸馏合成的上下文。内核 lane=None(stats=全账号);车道 lane=subtype(stats=该车道)。

    grounding = 档案层全量池信号(真爆文/读者需求/合规红线),跨样本校准,内核与各车道共用。
    """

    blogger: BloggerProfile
    user_info: dict[str, Any]
    stats: dict[str, Any]
    mode: str
    settings: Settings
    lane: str | None = None
    grounding: dict[str, Any] | None = None


def _grounding_block(ctx: DistillContext) -> str:
    """把 grounding 渲染成提示词尾段;空则返回空串。"""
    text = render_grounding(ctx.grounding)
    return f"\n\n档案信号（全量池·跨样本校准）：\n{text}" if text else ""


# ============================ 内核(认知 / 策略 / 人设) ============================

@prompt("distill.core.system", version="2026-07-10", kind="agent_system", owner="pinjie")
def build_core_system(ctx: DistillContext) -> str:
    """内核蒸馏的**系统契约**:引擎角色 + 硬边界 + 输出 schema。稳定、可缓存、只依赖 mode(受信);
    不含任何抓取数据 —— 与 user 里的样本证据分层,抵御证据中夹带的注入指令。"""
    if ctx.mode == "B":
        mode_framing = (
            "模式 B：诊断我的账号。下面这个账号就是用户本人的账号,目标不是模仿别人,而是照镜子——"
            "指出账号已做对的地方、明显短板、可立即执行的增长动作。self_diagnosis 必填且具体可执行。"
        )
    else:
        mode_framing = (
            "模式 A：拆解对标博主。把对标博主的公开内容提炼成用户可借鉴、可迁移的认知与策略。"
            "self_diagnosis 返回空对象(用户本人不是这个账号)。"
        )
    return f"""你是“博主蒸馏器”的分析引擎,这一步只提炼**「这个人」**——TA 怎么想、是什么人设、用什么声音表达、从什么角度选题。
**不要**写标题公式/正文结构/语言 DNA 这些「怎么写」的内容(那是另一步按模态分别蒸的);
**也不要**写发布节奏/数据趋势这类账号统计事实(那由档案层从全量数据算,不从样本蒸)。

{mode_framing}

<rules>
- 不能冒充原博主、不能复制原文原标题原经历;只提炼公开内容里的信念、立场、人设与表达声音。
- 每条结论都要贴 <evidence> 里的事实与数字,不要正确的废话;空缺给空数组,不要编造。
- 图内文字以内容性要点为准;装饰/引导字(点赞收藏关注、水印、背景杂字)不当方法论。
- 「档案信号」里的合规红线是会被平台限流/违规的写法:只可在 do_not_do 里点一句提醒,**绝不**写进认知金句、选题方法或价值立场。
- {anti_injection("<evidence>", "<blogger>")}
</rules>

<quality_bar>
最大的翻车点是「正确的废话」。以下只示范**质量标准**,不是内容来源,别把这里的字搬进结果:
- one_glance　差:「内容优质、很受欢迎」｜好:贴数字+机制,如「靠某系列 N 个月涨粉数万、单条最高上万赞——把某群体不懂的痛点做成可照做的教程」
- topic_method　差:「分享某领域知识」｜好:可迁移的决策方法,如「从已验证爆款反推可复用结构,再换一个同类痛点套同一模板」
- core_beliefs　差:「要真诚 / 要努力」｜好:具体且反共识的信念,如「某群体的无力感本质是缺『具体怎么做』的说明书,不是缺意愿」
</quality_bar>

{output_schema(render_schema(CoreDistillation), preface="只输出下面这个 JSON（字段齐全；不确定的列表给空数组）：")}"""


def build_core_prompt(ctx: DistillContext) -> str:
    """内核蒸馏的**证据(user)**:只放本次抓取数据;角色/硬边界/schema 契约在 build_core_system。"""
    blogger = ctx.blogger
    return f"""<blogger>
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description, "platform": blogger.platform}, ensure_ascii=False)}
</blogger>

<tikhub_user_info>
{json.dumps(ctx.user_info, ensure_ascii=False, default=str)[:2500]}
</tikhub_user_info>

<evidence>
全账号·跨模态;已按优先级装配:账号概览/观点金句池/爆款证据块/代表样本。
{render_stats_digest(ctx.stats, char_budget=ctx.settings.distill_evidence_char_budget, scope="core", legacy=ctx.settings.distill_evidence_legacy)}{_grounding_block(ctx)}
</evidence>

据 <evidence> 提炼这个人,按系统消息给定的契约与 JSON 结构输出,只输出该 JSON。"""


# ============================ 车道(内容层,按模态) ============================

_LANE_FRAMING: dict[str, str] = {
    IMAGE_TEXT: (
        "**图文笔记**车道。写法藏在:标题、正文结构、封面文案、排版、书面语言 DNA。\n"
        "- body_structures 基于 body_text/body_excerpt 分析正文骨架;video_script_structures 留空数组。\n"
        "- language_dna 每条以「书面：」开头。\n"
        "- 充分用视觉证据(封面钩子/版式/图内要点逐张):图内要点常才是真钩子——据此提炼 cover_text_rules 与 visual_layout_patterns,别只盯正文。"
    ),
    VIDEO: (
        "**视频**车道(口播+非口播统一在这蒸)。视频两面,按证据自适应加权:\n"
        "- **话术**(有转写时):开场钩子/信息密度/节奏/结尾/口语 DNA → 写进 video_script_structures;language_dna 以「口播：」开头、只依据 transcript;转写少/无就别硬凑。\n"
        "- **拍法**(证据带「视频拍法」时:镜头数/cuts·min/景别/出镜/字幕/转场/开头3秒/风格)→ 把分镜与节奏结构也写进 video_script_structures(如「开头3秒怼脸抛问题→中段快切特写→结尾拉远」「均~2s/镜的快剪」)。\n"
        "- body_structures 留空数组;**拍法只进 video_script_structures,别重复进 language_dna**(language_dna 只写口播语言特征,无口播就留空)。\n"
        "- 没有拍法证据的视频:只做话术+封面,别编分镜。"
    ),
}

@prompt("distill.lane.system", version="2026-07-10", kind="agent_system", owner="pinjie")
def build_lane_system(ctx: DistillContext) -> str:
    """车道内容层的**系统契约**:角色 + 硬边界 + 车道说明 + 输出 schema。只依赖 lane(受信),证据在 user。"""
    lane = ctx.lane or IMAGE_TEXT
    framing = _LANE_FRAMING.get(lane, _LANE_FRAMING[IMAGE_TEXT])
    return f"""你在蒸馏一个博主某一种内容形态的**写法(内容层)**——只写「怎么写」,不重复认知/人设(那是内核那步的事)。

车道说明:
{framing}

<rules>
- 不复制原文原标题;每条都贴 <evidence> 的事实,空缺给空数组、不编造。
- 图内文字以内容性要点为准;装饰/引导字(点赞收藏关注、水印)不当方法论。
- 「档案信号」里的合规红线**绝不**写进标题公式/语言DNA/封面文案/CTA。
- {anti_injection("<evidence>", "<blogger>")}
</rules>

<quality_bar>
翻车点是「正确的废话」,以下只示范质量标准、跨领域中性例子、非内容来源(别把这里的字搬进结果):
- title_formulas　差:「用数字做标题」｜好:可直接套的模板骨架,如「N个[领域]误区,第M个最坑」或「[身份]才懂的[场景]清单」
- reusable_tactic　差:「标题吸引人」｜好:说清为什么火的机制,如「用反常识数字制造认知缺口→正文逐条兑现→评论区追问下一篇」
</quality_bar>

{output_schema(render_schema(LaneContent), preface="只输出下面这个 JSON（字段齐全；不确定的列表给空数组）：")}"""


def build_lane_prompt(ctx: DistillContext) -> str:
    """车道内容层的**证据(user)**:只放该车道抓取数据;角色/边界/schema 契约在 build_lane_system。"""
    lane = ctx.lane or IMAGE_TEXT
    return f"""<blogger>
{ctx.blogger.display_name}（{ctx.blogger.platform}）｜车道：{subtype_label(lane)}
</blogger>

<evidence>
该车道证据(已按优先级装配;爆款证据块用「来源:external_id」标来源)。
{render_stats_digest(ctx.stats, char_budget=ctx.settings.distill_evidence_char_budget, scope="lane", legacy=ctx.settings.distill_evidence_legacy)}{_grounding_block(ctx)}
</evidence>

据 <evidence> 提炼该车道的写法,按系统消息给定的契约与 JSON 结构输出,只输出该 JSON。"""


# ============================ 传感器 / 评审 ============================

class CoreSchemaSensor:
    """内核阻断传感器:认知层至少有内容,否则强制修订。"""

    name = "内核完整性"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        cognitive = result.get("cognitive_layer", {}) or {}
        if not any(cognitive.get(k) for k in _COGNITIVE_KEYS):
            msg = "认知层三个子项全空,至少补全核心信念与观点张力"
            return SensorResult(passed=False, issues=[msg], corrective_feedback=msg)
        return SensorResult(passed=True)


class CoreQualitySensor:
    name = "内核质量"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        quality = evaluate_core_quality(result, ctx.stats, ctx.mode)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


class LaneSchemaSensor:
    """车道阻断传感器:标题公式或某种结构非空(非口播车道放宽:只要标题/封面有内容)。"""

    name = "车道完整性"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        if ctx.lane == VIDEO:
            # 视频车道容纳口播/非口播:标题公式、或视频脚本/分镜结构、或封面文案 任一非空即可。
            ok = bool(result.get("title_formulas") or result.get("video_script_structures") or result.get("cover_text_rules"))
            msg = "视频车道至少补全标题公式,或视频脚本/分镜结构,或封面文案"
        else:
            ok = bool(result.get("title_formulas") or result.get("body_structures") or result.get("video_script_structures"))
            msg = "内容层缺少标题公式与正文结构,至少补全标题公式与一种结构"
        return SensorResult(passed=ok, issues=[] if ok else [msg], corrective_feedback="" if ok else msg)


class LaneQualitySensor:
    name = "车道质量"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        quality = evaluate_lane_quality(result, ctx.stats, ctx.lane or IMAGE_TEXT)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


_CRITIC_FOCUS: dict[str, str] = {
    "core": "认知不够锋利、与统计矛盾、空泛无据、人设含糊",
    "lane": "标题公式空泛、结构与统计矛盾、把视频当图文/图文当视频、爆款拆解缺来源标注",
}


@prompt("distill.critic", version="2026-07-10", kind="critic", owner="pinjie")
def _critic_system(kind: str) -> str:
    """蒸馏评审的**系统契约**:角色 + 评审重点 + 输出 feedback 契约 + 抗注入。只依赖 kind(受信)。"""
    focus = _CRITIC_FOCUS.get(kind, _CRITIC_FOCUS["core"])
    return f"""你是博主蒸馏结果的资深审稿人。对照 <stats>,评审 <distillation_result> 里的蒸馏 JSON,挑出最多 5 条最该改进的问题({focus}),每条给出具体怎么改。
{anti_injection("<stats>", "<distillation_result>")}
只输出 JSON:{{"feedback": "一段中文纠错指令,分条列出问题与改法"}}"""


def _make_critic(settings: Settings, model: str | None, kind: str) -> Critic:
    """推理型评审:让模型对结果挑刺,产出面向模型的纠错指令。契约在 system,统计+结果(数据)在 user。"""
    system = _critic_system(kind)

    def critic(result: dict[str, Any], ctx: DistillContext) -> str:
        prompt = f"""<stats>
{json.dumps(ctx.stats, ensure_ascii=False, default=str)[:6000]}
</stats>

<distillation_result>
{json.dumps(result, ensure_ascii=False, default=str)[:6000]}
</distillation_result>

据 <stats> 审 <distillation_result>,只输出 feedback JSON。"""
        data = create_json_response(settings, prompt, model=model, system=system)
        feedback = data.get("feedback")
        return str(feedback).strip() if isinstance(feedback, str) else ""

    return critic


# ============================ 对外:内核 / 车道 蒸馏 ============================

def _budget(settings: Settings) -> SynthesisBudget:
    return SynthesisBudget(
        max_attempts=1 + max(0, settings.synthesis_max_revise_iterations),
        min_score=settings.synthesis_min_quality_score,
    )


def distill_core(
    settings: Settings,
    blogger: BloggerProfile,
    user_info: dict[str, Any],
    stats: dict[str, Any],
    mode: str,
    on_event: Any = None,
    grounding: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], SynthesisTrace]:
    """内核蒸馏(认知/策略/人设),吃全账号 stats + 档案 grounding。返回 (内核结果, 轨迹)。"""
    mode = normalize_mode(mode)
    ctx = DistillContext(blogger=blogger, user_info=user_info, stats=stats, mode=mode, settings=settings, lane=None, grounding=grounding)
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(name="内核蒸馏", build_prompt=build_core_prompt, build_system=build_core_system, normalize=lambda d, c: normalize_core(d, c.mode))
    sensors = [CoreSchemaSensor(), CoreQualitySensor()]
    critic = _make_critic(settings, model, "core") if settings.synthesis_llm_critic_enabled else None
    return run_synthesis(settings, guide, ctx, sensors, _budget(settings), model=model, critic=critic, on_event=on_event)


def distill_lane(
    settings: Settings,
    blogger: BloggerProfile,
    user_info: dict[str, Any],
    lane: str,
    lane_stats: dict[str, Any],
    mode: str,
    on_event: Any = None,
    grounding: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], SynthesisTrace]:
    """某条模态车道的内容层蒸馏,只吃该车道 stats + 档案 grounding(共用)。返回 (内容层结果, 轨迹)。"""
    ctx = DistillContext(blogger=blogger, user_info=user_info, stats=lane_stats, mode=normalize_mode(mode), settings=settings, lane=lane, grounding=grounding)
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(name=f"内容层·{subtype_label(lane)}", build_prompt=build_lane_prompt, build_system=build_lane_system, normalize=lambda d, c: normalize_lane(d))
    sensors = [LaneSchemaSensor(), LaneQualitySensor()]
    critic = _make_critic(settings, model, "lane") if settings.synthesis_llm_critic_enabled else None
    return run_synthesis(settings, guide, ctx, sensors, _budget(settings), model=model, critic=critic, on_event=on_event)


# ============================ 归一 ============================

_COGNITIVE_KEYS = ("core_beliefs", "opinion_tensions", "value_stance")


def normalize_core(data: dict[str, Any], mode: str) -> dict[str, Any]:
    """typed return:CoreDistillation 单一源做解析校验(等价旧 _as_list/填骨架),model_dump 回 dict 保下游接口。"""
    if not isinstance(data, dict):
        raise AIServiceError("内核蒸馏结果不是 JSON 对象")
    return CoreDistillation.model_validate(data).model_dump()


def normalize_lane(data: dict[str, Any]) -> dict[str, Any]:
    """typed return:LaneContent 单一源做解析校验,model_dump 回 dict 保下游接口。"""
    if not isinstance(data, dict):
        raise AIServiceError("车道内容层结果不是 JSON 对象")
    return LaneContent.model_validate(data).model_dump()


def is_core_empty(data: dict[str, Any]) -> bool:
    cognitive = data.get("cognitive_layer", {}) or {}
    return not any(cognitive.get(k) for k in _COGNITIVE_KEYS)


def is_lane_empty(data: dict[str, Any]) -> bool:
    return not any(data.get(k) for k in ("title_formulas", "opening_templates", "body_structures", "video_script_structures"))


# ============================ 质量分(内核 / 车道) ============================

def _grade(score: int) -> str:
    return "优" if score >= 85 else ("良" if score >= 70 else "待改进")


def evaluate_core_quality(core: dict[str, Any], stats: dict[str, Any], mode: str) -> dict[str, Any]:
    """内核质量:认知层覆盖 / 策略层覆盖 /(模式B）自我诊断。"""
    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    score = 100

    def deduct(amount: int, name: str, ok: bool, detail: str) -> None:
        nonlocal score
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            score -= amount
            issues.append(detail)

    cognitive = core.get("cognitive_layer", {})
    angle = core.get("angle_layer", {})
    voice = core.get("voice", {}) if isinstance(core.get("voice"), dict) else {}
    cognitive_items = sum(len(cognitive.get(k) or []) for k in _COGNITIVE_KEYS)
    deduct(30, "认知层覆盖", cognitive_items >= 3, f"认知层共 {cognitive_items} 条，建议 ≥3 条")
    angle_items = sum(len(angle.get(k) or []) for k in ("topic_method", "topic_angles", "trend_hijacking"))
    deduct(15, "选题思路覆盖", angle_items >= 2, f"选题思路共 {angle_items} 条，建议 ≥2 条(选题方法/角度是选题器的原料)")
    has_voice = bool(str(voice.get("self_ref") or "").strip() or voice.get("catchphrases"))
    deduct(10, "人设声音", has_voice, "voice 为空:至少给出自称方式或口头禅(创作借声要用)")
    if not str(core.get("one_glance") or "").strip():
        deduct(10, "一眼看清", False, "one_glance 为空")
    if mode == "B":
        diag = core.get("self_diagnosis", {})
        diag_items = sum(len(diag.get(k) or []) for k in ("strengths", "weaknesses", "action_plan"))
        deduct(15, "自我诊断(模式B)", diag_items >= 3, f"诊断模式但 self_diagnosis 仅 {diag_items} 条")
    score = max(0, min(100, score))
    return {"score": score, "grade": _grade(score), "issues": issues, "checks": checks}


def evaluate_lane_quality(content: dict[str, Any], lane_stats: dict[str, Any], lane: str) -> dict[str, Any]:
    """某车道内容层质量:标题公式 / 结构 / 爆款拆解 / 空泛。非口播车道对「结构」放宽。"""
    issues: list[str] = []
    checks: list[dict[str, Any]] = []
    score = 100

    def deduct(amount: int, name: str, ok: bool, detail: str) -> None:
        nonlocal score
        checks.append({"name": name, "ok": ok, "detail": detail})
        if not ok:
            score -= amount
            issues.append(detail)

    title_count = len(content.get("title_formulas") or [])
    deduct(25, "标题公式", title_count >= 3, f"标题公式 {title_count} 条，建议 ≥3 条")
    has_body = bool(content.get("body_structures"))
    has_video = bool(content.get("video_script_structures"))
    if lane == VIDEO:
        deduct(20, "视频脚本/分镜结构", has_video or bool(content.get("cover_text_rules")), "视频脚本/分镜结构与封面文案均空")
    else:
        deduct(20, "正文结构", has_body, "图文正文结构为空")
    breakdowns = content.get("top_post_breakdowns") or []
    hot_available = len(lane_stats.get("hot_posts") or [])
    expected = min(3, hot_available) if hot_available else 0
    deduct(20, "TOP爆款拆解", len(breakdowns) >= expected, f"爆款逐条拆解 {len(breakdowns)} 条，建议 ≥{expected} 条")
    sourced = sum(1 for item in breakdowns if isinstance(item, dict) and str(item.get("source") or "").strip())
    deduct(10, "来源标注", expected == 0 or sourced >= 1, "爆款拆解缺少来源标注(source)")
    content_items = [str(x) for k in ("title_formulas", "opening_templates", "language_dna", "cta_strategy") for x in (content.get(k) or [])]
    short_items = sum(1 for x in content_items if len(x.strip()) < 8)
    vague_ok = not content_items or short_items / max(len(content_items), 1) < 0.4
    deduct(15, "空泛检测", vague_ok, f"内容层有 {short_items}/{len(content_items)} 条过短，疑似空泛")
    score = max(0, min(100, score))
    return {"score": score, "grade": _grade(score), "issues": issues, "checks": checks, "lane": lane}
