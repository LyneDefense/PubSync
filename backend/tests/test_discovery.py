from app.benchmark_discovery import querygen
from app.benchmark_discovery.querygen import expand_directions
from app.benchmark_discovery.ranking import CandidateSignals, composite_score, rank
from app.benchmark_discovery.recall import WeightedDomain, merge_interleave_dedupe, recall
from app.blogger_distillation.search import BloggerSearchResult
from app.config import Settings


def _r(ext: str, followers: int = 1000) -> BloggerSearchResult:
    return BloggerSearchResult(
        platform="xhs", external_id=ext, display_name=ext, homepage_url=f"h/{ext}",
        avatar_url="", description="", follower_count=followers, raw={},
    )


# ——— ranking ———
def test_composite_score_popular_and_matched_beats_weak():
    strong = CandidateSignals(external_id="a", follower_count=50000, like_samples=[800, 1200], matched_weight=80)
    weak = CandidateSignals(external_id="b", follower_count=200, like_samples=[2], matched_weight=10)
    assert composite_score(strong) > composite_score(weak)


def test_inactive_and_institution_downweighted():
    base = CandidateSignals(external_id="a", follower_count=10000, like_samples=[300], matched_weight=60)
    inactive = CandidateSignals(external_id="a", follower_count=10000, like_samples=[300], matched_weight=60, active=False)
    org = CandidateSignals(external_id="a", follower_count=10000, like_samples=[300], matched_weight=60, is_personal=False)
    assert composite_score(inactive) < composite_score(base)
    assert composite_score(org) < composite_score(base)


def test_seed_similarity_boosts_rank():
    like = CandidateSignals(external_id="like", follower_count=8000, like_samples=[200], matched_weight=50, similarity_to_seed=95)
    unlike = CandidateSignals(external_id="unlike", follower_count=8000, like_samples=[200], matched_weight=50, similarity_to_seed=10)
    ranked = rank([unlike, like])
    assert ranked[0][0] == "like"


# ——— recall: 交错去重 + 排除 + 截断 ———
def test_merge_interleave_dedupe_excludes_and_caps():
    users = [_r("u1"), _r("u2"), _r("dup")]
    authors = [_r("dup"), _r("a1"), _r("a2")]   # dup 与 users 重复,只取一次
    following = [_r("f1")]
    out = merge_interleave_dedupe([users, authors, following], exclude_ids={"u2"}, cap=4)
    ids = [r.external_id for r in out]
    assert "u2" not in ids          # 被排除
    assert ids.count("dup") == 1    # 去重
    assert len(out) == 4            # 截断
    # round-robin:第一轮各通道取一个 → u1, dup, f1, 然后 u2被排, a1
    assert ids[0] == "u1" and "f1" in ids


def test_recall_runs_all_channels_and_survives_channel_failure():
    def users_fn(kw):
        return [_r(f"user-{kw}")]

    def authors_fn(kw):
        raise RuntimeError("note search down")   # B 路挂了不应阻断

    out = recall(
        [WeightedDomain("香港保险", 80), WeightedDomain("储蓄险", 50)],
        search_users_fn=users_fn,
        search_notes_authors_fn=authors_fn,
        seed_following=[_r("seed-follow")],
        cap=10,
        exclude_ids=(),
    )
    ids = {r.external_id for r in out}
    assert "user-香港保险" in ids and "user-储蓄险" in ids   # A 路两个方向都跑了
    assert "seed-follow" in ids                              # C 路在
    # B 路抛错被吞,不影响其它


# ——— querygen: 方向扩展 + LLM 失败兜底 ———
def test_expand_directions_parses_and_marks_top4(monkeypatch):
    def fake_llm(settings, prompt):
        return {"directions": [
            {"label": "储蓄险科普", "weight": 90, "reason": "贴近"},
            {"label": "香港身份", "weight": 70},
            {"label": "保险避坑", "weight": 60},
            {"label": "家庭配置", "weight": 40},
            {"label": "基金股票", "weight": 20},
        ]}
    monkeypatch.setattr(querygen, "create_json_response", fake_llm)
    dirs = expand_directions(Settings(), ["香港保险"], max_directions=10)
    assert [d.label for d in dirs][:1] == ["储蓄险科普"]        # 按权重降序
    assert sum(1 for d in dirs if d.selected) == 4              # 默认勾 top4
    assert dirs[-1].label == "基金股票" and not dirs[-1].selected


def test_expand_directions_falls_back_on_llm_failure(monkeypatch):
    def boom(settings, prompt):
        raise RuntimeError("llm down")
    monkeypatch.setattr(querygen, "create_json_response", boom)
    dirs = expand_directions(Settings(), ["香港保险", "保险经纪"])
    assert [d.label for d in dirs] == ["香港保险", "保险经纪"]   # 退回原始领域
    assert all(d.selected for d in dirs)


def test_expand_directions_empty_domains():
    assert expand_directions(Settings(), ["  ", ""]) == []
