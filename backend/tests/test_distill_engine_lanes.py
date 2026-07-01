"""车道化蒸馏引擎:内核/车道 prompt 字段、normalize、按车道质量分(纯函数,无 LLM)。"""

from types import SimpleNamespace as N

from app.blogger_distillation.modality import IMAGE_TEXT, TALKING_VIDEO, VISUAL_VIDEO
from app.blogger_distillation.service.distill_engine import (
    DistillContext,
    build_core_prompt,
    build_lane_prompt,
    evaluate_core_quality,
    evaluate_lane_quality,
    normalize_core,
    normalize_lane,
)

_BL = N(display_name="阿甜", homepage_url="http://x", niche="运营", description="", platform="xhs")


def _ctx(stats, lane=None, mode="A"):
    return DistillContext(blogger=_BL, user_info={}, stats=stats, mode=mode, lane=lane)


def test_core_prompt_has_cognitive_not_content():
    p = build_core_prompt(_ctx({"sample_count": 10}))
    assert "cognitive_layer" in p and "strategy_layer" in p
    assert "title_formulas" not in p  # 内核不含内容层


def test_lane_prompt_framing_by_modality():
    assert "口播脚本" in build_lane_prompt(_ctx({}, lane=TALKING_VIDEO))
    assert "图文笔记" in build_lane_prompt(_ctx({}, lane=IMAGE_TEXT))
    assert "视觉 craft" in build_lane_prompt(_ctx({}, lane=VISUAL_VIDEO))  # 非口播诚实边界
    assert "title_formulas" in build_lane_prompt(_ctx({}, lane=IMAGE_TEXT))


def test_normalize_core_fills_skeleton():
    out = normalize_core({"cognitive_layer": {"core_beliefs": "单条转列表"}}, "A")
    assert out["cognitive_layer"]["core_beliefs"] == ["单条转列表"]
    assert out["strategy_layer"]["posting_rhythm"] == ""
    assert isinstance(out["persona"], dict) and out["self_diagnosis"]["strengths"] == []


def test_normalize_lane_lists():
    out = normalize_lane({"title_formulas": "一条", "top_post_breakdowns": None})
    assert out["title_formulas"] == ["一条"] and out["top_post_breakdowns"] == []


def test_core_quality_counts_cognitive():
    good = {"cognitive_layer": {"core_beliefs": ["a", "b"], "opinion_tensions": ["c"], "value_stance": ["d"]},
            "strategy_layer": {"series_planning": ["s1"], "ops_habits": ["s2"]}, "one_glance": "有"}
    q = evaluate_core_quality(good, {}, "A")
    assert q["score"] >= 85 and q["grade"] == "优"
    thin = evaluate_core_quality({"cognitive_layer": {}, "strategy_layer": {}}, {}, "A")
    assert thin["score"] < 85 and thin["issues"]


def test_lane_quality_visual_relaxed():
    # 非口播车道:没有正文/口播结构不该被重罚,只要标题/封面/标签有内容。
    content = {"title_formulas": ["t1", "t2", "t3"], "cover_text_rules": ["封面"], "top_post_breakdowns": []}
    q = evaluate_lane_quality(content, {"hot_posts": []}, VISUAL_VIDEO)
    assert q["score"] >= 70
    # 口播车道:缺结构会扣「正文/口播结构」分
    q2 = evaluate_lane_quality({"title_formulas": ["a", "b", "c"], "top_post_breakdowns": []}, {"hot_posts": []}, TALKING_VIDEO)
    assert any("结构" in i for i in q2["issues"])
