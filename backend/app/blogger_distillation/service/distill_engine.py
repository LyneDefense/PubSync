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

from app.blogger_distillation.modality import (
    IMAGE_TEXT,
    TALKING_VIDEO,
    VISUAL_VIDEO,
    subtype_label,
)
from app.config import Settings
from app.models import BloggerProfile
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
    """一次蒸馏合成的上下文。内核 lane=None(stats=全账号);车道 lane=subtype(stats=该车道)。"""

    blogger: BloggerProfile
    user_info: dict[str, Any]
    stats: dict[str, Any]
    mode: str
    lane: str | None = None


# ============================ 内核(认知 / 策略 / 人设) ============================

def build_core_prompt(ctx: DistillContext) -> str:
    """内核提示词:认知层 / 策略层 / 人设 / 价值立场 / 诊断——人的层面,不含内容层。"""
    blogger = ctx.blogger
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
    return f"""
你是“博主蒸馏器”的分析引擎,这一步只提炼**「这个人」**——TA 怎么想、怎么运营、是什么人设。
**不要**写标题公式/正文结构/语言 DNA 这些「怎么写」的内容(那是另一步按模态分别蒸的)。

{mode_framing}

硬边界：
- 不能冒充原博主、不能复制原文原标题原经历;只提炼公开内容里的信念、立场、思维、运营策略。
- 输出必须是合法 JSON 对象,不要 Markdown/HTML/解释/<think>。
- 每条结论尽量贴着“代码统计与代表样本”的事实与数字,不要正确的废话;空缺给空数组,不要编造。

博主：
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description, "platform": blogger.platform}, ensure_ascii=False)}

TikHub 用户信息摘要：
{json.dumps(ctx.user_info, ensure_ascii=False, default=str)[:2500]}

代码统计与代表样本(全账号,跨模态)：
{json.dumps(ctx.stats, ensure_ascii=False, default=str)[:16000]}

只输出下面这个 JSON（字段齐全；不确定的列表给空数组）：
{{
  "one_glance": "一句话说清这个账号的价值和爆款原因（带关键数字）",
  "persona": {{"identity": "身份感/人设", "stance": "表达姿态", "trust_source": "信任来源"}},
  "audience": "目标读者画像",
  "cognitive_layer": {{
    "core_beliefs": ["核心信念：TA 默认相信什么"],
    "opinion_tensions": ["观点张力/反共识：TA 常对抗的常识"],
    "value_stance": ["价值立场"],
    "thinking_models": ["反复出现的思维模式"]
  }},
  "strategy_layer": {{
    "series_planning": ["系列/选题规划方式"],
    "trend_hijacking": ["蹭热点/借势方式"],
    "ops_habits": ["运营习惯：发布、互动、引导"],
    "posting_rhythm": "发布节奏一句话总结（结合 frequency_info）"
  }},
  "comment_insights": ["评论区暴露的读者真实需求和互动机会"],
  "growth_trend": "结合 growth_trend/数据面板的发展趋势与机会，一段话",
  "sample_topics": ["可迁移到用户自己账号的新选题示例 TOP8"],
  "do_not_do": ["创作禁区/不该模仿的部分"],
  "self_diagnosis": {{"strengths": ["模式B：账号优势"], "weaknesses": ["模式B：明显短板"], "action_plan": ["模式B：可立即执行的增长动作"]}},
  "core_conclusion": "给用户的核心使用建议（一段话）"
}}
"""


# ============================ 车道(内容层,按模态) ============================

_LANE_FRAMING: dict[str, str] = {
    IMAGE_TEXT: (
        "这是**图文笔记**车道。写法藏在:标题、正文结构、封面文案、排版、书面语言 DNA。"
        "body_structures 基于 body_text/body_excerpt 分析正文骨架;video_script_structures 留空数组。"
        "language_dna 每条以「书面：」开头。"
    ),
    TALKING_VIDEO: (
        "这是**口播视频**车道(人对着镜头讲述/教学,说的话即内容)。写法藏在:口播脚本"
        "(开场钩子、信息密度、讲述节奏、结尾)、标题、封面、口语语言 DNA。"
        "把结构写进 video_script_structures(基于 transcript);body_structures 留空数组。"
        "language_dna 每条以「口播：」开头,只依据 transcript,不要写成「正文几千字」。"
    ),
    VISUAL_VIDEO: (
        "这是**非口播视频**车道(剧情/卡点/vlog/展示,画面为主、台词很少)。**诚实边界**:"
        "纯文本只能可靠给出 标题公式 / 封面文案 / 标签策略 / 发布节奏;"
        "画面、卡点、运镜、BGM 这类视觉 craft **无法从文本蒸出**——相关字段给空数组,"
        "并在 body_structures 里放一条「视觉打法需人工或视觉模型分析,本次基于文本未覆盖」。"
        "video_script_structures 若几乎无转写则留空。"
    ),
}


def build_lane_prompt(ctx: DistillContext) -> str:
    """车道提示词:该模态的内容层「怎么写」。ctx.stats 是该车道的 stats,ctx.lane 是 subtype。"""
    lane = ctx.lane or IMAGE_TEXT
    framing = _LANE_FRAMING.get(lane, _LANE_FRAMING[IMAGE_TEXT])
    return f"""
你在蒸馏一个博主某一种内容形态的**写法(内容层)**。只写「怎么写」,不要重复认知/人设(那是内核那步的事)。

车道说明:{framing}

硬边界：合法 JSON;不复制原文原标题;贴“该车道统计与代表样本”的事实;空缺给空数组,不编造。

博主：{ctx.blogger.display_name}（{ctx.blogger.platform}）｜车道：{subtype_label(lane)}

该车道统计与代表样本(含 hot_posts 爆款,可用 title/external_id/score 标来源)：
{json.dumps(ctx.stats, ensure_ascii=False, default=str)[:16000]}

只输出下面这个 JSON（字段齐全；不确定的列表给空数组）：
{{
  "title_formulas": ["标题公式 TOP5，结合 title_patterns 的占比"],
  "opening_templates": ["开头模板 TOP3，结合 opening_patterns"],
  "body_structures": ["图文正文结构，只能基于 body_text；非图文车道见车道说明"],
  "video_script_structures": ["视频口播/字幕结构，只能基于 transcript；无转写则空数组"],
  "emotional_rhythm": ["情绪节奏/留人钩子公式"],
  "language_dna": ["语言 DNA：高频表达、句式节奏、人称策略、口头禅（按车道说明加「书面：」/「口播：」前缀）"],
  "cta_strategy": ["CTA/互动引导策略，结合 cta_patterns"],
  "cover_text_rules": ["封面文案规律"],
  "hashtag_strategy": ["标签策略，结合 frequent_hashtags"],
  "top_post_breakdowns": [
    {{"rank": 1, "title_ref": "该车道爆款样本标题(可截断)", "source": "external_id 或标题", "why_viral": "为什么火（贴数据）", "reusable_tactic": "可复用的具体技巧"}}
  ]
}}
"""


# ============================ 传感器 / 评审 ============================

class CoreSchemaSensor:
    """内核阻断传感器:认知层至少有内容,否则强制修订。"""

    name = "内核完整性"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        cognitive = result.get("cognitive_layer", {}) or {}
        if not any(cognitive.get(k) for k in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models")):
            msg = "认知层四个子项全空,至少补全核心信念与观点张力"
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
        if ctx.lane == VISUAL_VIDEO:
            ok = bool(result.get("title_formulas") or result.get("cover_text_rules") or result.get("hashtag_strategy"))
            msg = "非口播车道至少补全标题公式或封面文案"
        else:
            ok = bool(result.get("title_formulas") or result.get("body_structures") or result.get("video_script_structures"))
            msg = "内容层缺少标题公式与正文/口播结构,至少补全标题公式与一种结构"
        return SensorResult(passed=ok, issues=[] if ok else [msg], corrective_feedback="" if ok else msg)


class LaneQualitySensor:
    name = "车道质量"

    def check(self, result: dict[str, Any], ctx: DistillContext) -> SensorResult:
        quality = evaluate_lane_quality(result, ctx.stats, ctx.lane or IMAGE_TEXT)
        feedback = "；".join(quality["issues"]) if quality["issues"] else ""
        return SensorResult(passed=True, score=quality["score"], issues=quality["issues"], corrective_feedback=feedback)


def _make_critic(settings: Settings, model: str | None, kind: str) -> Critic:
    """推理型评审:让模型对结果挑刺,产出面向模型的纠错指令。kind=内核/车道 只影响提示语。"""

    def critic(result: dict[str, Any], ctx: DistillContext) -> str:
        focus = (
            "认知不够锋利、与统计矛盾、空泛无据、人设含糊"
            if kind == "core"
            else "标题公式空泛、结构与统计矛盾、把视频当图文/图文当视频、爆款拆解缺来源标注"
        )
        prompt = f"""你是博主蒸馏结果的资深审稿人。下面是一份蒸馏 JSON 和原始统计。
请挑出最多 5 条最该改进的问题（{focus}），每条给出具体怎么改。
只输出 JSON：{{"feedback": "一段中文纠错指令，分条列出问题与改法"}}

原始统计：{json.dumps(ctx.stats, ensure_ascii=False, default=str)[:6000]}
蒸馏结果：{json.dumps(result, ensure_ascii=False, default=str)[:6000]}
"""
        data = create_json_response(settings, prompt, model=model)
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
) -> tuple[dict[str, Any], SynthesisTrace]:
    """内核蒸馏(认知/策略/人设),吃全账号 stats。返回 (内核结果, 轨迹)。"""
    mode = normalize_mode(mode)
    ctx = DistillContext(blogger=blogger, user_info=user_info, stats=stats, mode=mode, lane=None)
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(name="内核蒸馏", build_prompt=build_core_prompt, normalize=lambda d, c: normalize_core(d, c.mode))
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
) -> tuple[dict[str, Any], SynthesisTrace]:
    """某条模态车道的内容层蒸馏,只吃该车道 stats。返回 (内容层结果, 轨迹)。"""
    ctx = DistillContext(blogger=blogger, user_info=user_info, stats=lane_stats, mode=normalize_mode(mode), lane=lane)
    model = (settings.distill_text_model or "").strip() or None
    guide = TaskGuide(name=f"内容层·{subtype_label(lane)}", build_prompt=build_lane_prompt, normalize=lambda d, c: normalize_lane(d))
    sensors = [LaneSchemaSensor(), LaneQualitySensor()]
    critic = _make_critic(settings, model, "lane") if settings.synthesis_llm_critic_enabled else None
    return run_synthesis(settings, guide, ctx, sensors, _budget(settings), model=model, critic=critic, on_event=on_event)


# ============================ 归一 ============================

_CORE_LAYERS: dict[str, list[str]] = {
    "cognitive_layer": ["core_beliefs", "opinion_tensions", "value_stance", "thinking_models"],
    "strategy_layer": ["series_planning", "trend_hijacking", "ops_habits", "posting_rhythm"],
}
_LANE_LIST_KEYS = [
    "title_formulas", "opening_templates", "body_structures", "video_script_structures",
    "emotional_rhythm", "language_dna", "cta_strategy", "cover_text_rules", "hashtag_strategy",
]


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else ([] if value in (None, "") else [value])


def normalize_core(data: dict[str, Any], mode: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AIServiceError("内核蒸馏结果不是 JSON 对象")
    for layer, keys in _CORE_LAYERS.items():
        layer_value = data.get(layer) if isinstance(data.get(layer), dict) else {}
        for key in keys:
            if key == "posting_rhythm":
                layer_value.setdefault(key, "")
            else:
                layer_value[key] = _as_list(layer_value.get(key))
        data[layer] = layer_value
    persona = data.get("persona")
    if not isinstance(persona, dict):
        data["persona"] = {"identity": str(persona or ""), "stance": "", "trust_source": ""}
    data.setdefault("one_glance", "")
    data.setdefault("audience", "")
    for list_key in ("comment_insights", "sample_topics", "do_not_do"):
        data[list_key] = _as_list(data.get(list_key))
    data.setdefault("growth_trend", "")
    data.setdefault("core_conclusion", "")
    diagnosis = data.get("self_diagnosis") if isinstance(data.get("self_diagnosis"), dict) else {}
    for key in ("strengths", "weaknesses", "action_plan"):
        diagnosis[key] = _as_list(diagnosis.get(key))
    data["self_diagnosis"] = diagnosis
    return data


def normalize_lane(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise AIServiceError("车道内容层结果不是 JSON 对象")
    for key in _LANE_LIST_KEYS:
        data[key] = _as_list(data.get(key))
    data["top_post_breakdowns"] = _as_list(data.get("top_post_breakdowns"))
    return data


def is_core_empty(data: dict[str, Any]) -> bool:
    cognitive = data.get("cognitive_layer", {}) or {}
    return not any(cognitive.get(k) for k in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models"))


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
    strategy = core.get("strategy_layer", {})
    cognitive_items = sum(len(cognitive.get(k) or []) for k in ("core_beliefs", "opinion_tensions", "value_stance", "thinking_models"))
    deduct(30, "认知层覆盖", cognitive_items >= 4, f"认知层共 {cognitive_items} 条，建议 ≥4 条")
    strategy_items = sum(len(strategy.get(k) or []) for k in ("series_planning", "trend_hijacking", "ops_habits"))
    deduct(15, "策略层覆盖", strategy_items >= 2, f"策略层共 {strategy_items} 条，建议 ≥2 条")
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
    if lane == VISUAL_VIDEO:
        deduct(10, "封面/标签", bool(content.get("cover_text_rules") or content.get("hashtag_strategy")), "非口播车道封面文案与标签策略均空")
    else:
        deduct(20, "正文/口播结构", has_body or has_video, "图文正文结构与视频口播结构均为空")
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
