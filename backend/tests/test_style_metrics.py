from app.skill_optimization import (
    attribution,
    build_profile,
    extract_features,
    gap_closed,
    style_similarity,
)

# 模拟"博主A:口语化、感叹号多、第一人称、emoji"
A_NOTES = [
    "姐妹们！我必须告诉你们这个方法😭 真的太香了！我用了一周就瘦了三斤！",
    "我又来分享啦！这次是干货！姐妹们一定要看到最后😍 我踩过的坑你们别再踩了！",
    "说真的我以前也不信！但我亲测有效！这个真的绝了😭 冲就完事了！",
]
# 博主B:冷静、长句、少标点、无 emoji、术语
B_NOTES = [
    "本文系统梳理了该方法的实现路径,并在三个维度上进行了对比分析与论证。",
    "从结构上看,该方案的核心在于分层解耦,从而降低了整体的维护成本。",
    "综上所述,在多数场景下该策略具备可复用性,但仍需结合具体约束评估。",
]


def test_extract_features_empty_and_counts():
    assert all(v == 0.0 for v in extract_features("").values())
    f = extract_features("太好了！真的吗？")
    assert f["exclaim_per100"] > 0
    assert f["question_per100"] > 0
    assert f["question_sent_ratio"] > 0


def test_own_style_scores_higher_than_other_style():
    profile_a = build_profile(A_NOTES)
    own = "我太激动了！姐妹们这个方法真的有效😭 一定要试试！"
    foreign = "本研究在若干维度上对该方法进行了严谨的对比与论证分析。"
    assert style_similarity(own, profile_a) > style_similarity(foreign, profile_a)


def test_off_modality_scores_near_zero():
    # 用 A 的画像去测一段完全不同文体/词汇的文本(模拟图文 vs 口播错配)
    profile_a = build_profile(A_NOTES)
    off = "第一章 绪论 1.1 背景 1.2 目的 1.3 方法 参考文献 附录"
    assert style_similarity(off, profile_a) < style_similarity(A_NOTES[0], profile_a)


def test_attribution_picks_right_blogger():
    profiles = {"A": build_profile(A_NOTES), "B": build_profile(B_NOTES)}
    a_like = "姐妹们！我亲测有效😭 真的太香了！"
    b_like = "本文从结构层面对该方案进行了系统的对比与论证。"
    assert attribution(a_like, profiles) == "A"
    assert attribution(b_like, profiles) == "B"


def test_attribution_empty_profiles():
    assert attribution("whatever", {}) is None


def test_gap_closed_math_and_clamp():
    assert gap_closed(20, 10, 30) == 50.0
    assert gap_closed(5, 10, 30) == 0.0      # 比 floor 还低 → 0
    assert gap_closed(40, 10, 30) == 100.0   # 超过 ceiling → 封顶 100
    assert gap_closed(15, 20, 20) == 0.0     # span=0 → 0


def test_empty_profile_similarity_zero():
    empty = build_profile([])
    assert style_similarity("任何文本", empty) == 0.0
    assert style_similarity("", build_profile(A_NOTES)) == 0.0
