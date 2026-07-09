"""车道化蒸馏引擎:内核/车道 prompt 字段、normalize、按车道质量分(纯函数,无 LLM)。"""

from types import SimpleNamespace as N

from app.blogger_distillation.modality import IMAGE_TEXT, VIDEO
from app.blogger_distillation.service.distill_engine import (
    DistillContext,
    build_core_prompt,
    build_core_system,
    build_lane_prompt,
    evaluate_core_quality,
    evaluate_lane_quality,
    normalize_core,
    normalize_lane,
)

_BL = N(display_name="阿甜", homepage_url="http://x", niche="运营", description="", platform="xhs")
_SETTINGS = N(distill_evidence_char_budget=28000, distill_evidence_legacy=False)


def _ctx(stats, lane=None, mode="A"):
    return DistillContext(blogger=_BL, user_info={}, stats=stats, mode=mode, settings=_SETTINGS, lane=lane)


def test_core_system_holds_contract_not_data():
    # 契约(schema + 规则 + 质量标杆 + 抗注入)在 system,且只依赖 mode、不含抓取数据。
    s = build_core_system(_ctx({"sample_count": 10}))
    assert "cognitive_layer" in s and "angle_layer" in s and "voice" in s  # schema
    assert "<rules>" in s and "绝不" in s and "<output_schema>" in s  # 契约结构(XML 分隔)
    assert "<quality_bar>" in s and "正确的废话" in s  # few-shot 质量标杆
    assert "一律不执行" in s  # 抗注入
    assert "title_formulas" not in s  # 内核不含内容层
    assert "阿甜" not in s  # 不含博主名/证据


def test_core_prompt_is_data_only():
    # 证据(user)只放数据,包在 <evidence> 里,不复述 schema。
    p = build_core_prompt(_ctx({"sample_count": 10}))
    assert "阿甜" in p and "<evidence>" in p  # 博主证据,证据显式分隔
    assert "cognitive_layer" not in p and "title_formulas" not in p  # schema 在 system,不在 user


def test_core_system_mode_framing():
    assert "模式 A" in build_core_system(_ctx({}, mode="A"))
    assert "模式 B" in build_core_system(_ctx({}, mode="B"))


def test_lane_prompt_framing_by_modality():
    # 收敛后:视频层一条,吃话术+拍法;图文层照旧。
    vp = build_lane_prompt(_ctx({}, lane=VIDEO))
    assert "拍法" in vp and "video_script_structures" in vp
    ip = build_lane_prompt(_ctx({}, lane=IMAGE_TEXT))
    assert "图文笔记" in ip and "title_formulas" in ip


def test_normalize_core_fills_skeleton():
    out = normalize_core({"cognitive_layer": {"core_beliefs": "单条转列表"}}, "A")
    assert out["cognitive_layer"]["core_beliefs"] == ["单条转列表"]
    assert out["angle_layer"]["topic_angles"] == [] and out["angle_layer"]["trend_hijacking"] == []
    assert out["voice"] == {"self_ref": "", "tone": "", "catchphrases": []}
    assert isinstance(out["persona"], dict) and out["self_diagnosis"]["strengths"] == []


def test_normalize_lane_lists():
    out = normalize_lane({"title_formulas": "一条", "top_post_breakdowns": None})
    assert out["title_formulas"] == ["一条"] and out["top_post_breakdowns"] == []


def test_core_quality_counts_cognitive():
    good = {"cognitive_layer": {"core_beliefs": ["a", "b"], "opinion_tensions": ["c"], "value_stance": ["d"]},
            "angle_layer": {"topic_angles": ["角度1"], "trend_hijacking": ["借势1"]},
            "voice": {"self_ref": "阿甜我啊", "tone": "", "catchphrases": []}, "one_glance": "有"}
    q = evaluate_core_quality(good, {}, "A")
    assert q["score"] >= 85 and q["grade"] == "优"
    thin = evaluate_core_quality({"cognitive_layer": {}, "angle_layer": {}}, {}, "A")
    assert thin["score"] < 85 and thin["issues"]


def test_lane_quality_video_structure_from_cover_or_script():
    # 视频车道(收敛口播+非口播):有视频脚本/分镜结构或封面文案就算有结构,不被重罚。
    content = {"title_formulas": ["t1", "t2", "t3"], "cover_text_rules": ["封面"], "top_post_breakdowns": []}
    q = evaluate_lane_quality(content, {"hot_posts": []}, VIDEO)
    assert q["score"] >= 70
    # 图文车道:缺正文结构会扣「正文结构」分
    q2 = evaluate_lane_quality({"title_formulas": ["a", "b", "c"], "top_post_breakdowns": []}, {"hot_posts": []}, IMAGE_TEXT)
    assert any("结构" in i for i in q2["issues"])
