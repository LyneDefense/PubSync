"""博主诊断·硬实力纯函数单测。"""

from datetime import datetime, timedelta, timezone

from app.appraisal.hard import (
    AccountStat,
    PostStat,
    _interp,
    hard_dimensions,
    score_activity,
    score_like_collect_ratio,
    score_reach,
    score_viral,
)
from app.appraisal.intent import suggest_intent
from app.appraisal.judge import judge_goal_fit, judge_note_relevance, judge_soft, judge_vertical

NOW = datetime(2026, 6, 26, tzinfo=timezone.utc)


def test_interp_clamps_and_interpolates():
    pts = [(0, 0), (1.5, 75), (3, 100)]
    assert _interp(-1, pts) == 0
    assert _interp(10, pts) == 100
    assert _interp(1.5, pts) == 75
    assert _interp(0.75, pts) == 37.5  # 中点


def test_reach_log_scale():
    assert score_reach(AccountStat(follower_count=1000)).score == 75
    assert score_reach(AccountStat(follower_count=100)).score == 50
    assert score_reach(AccountStat(follower_count=0)).score == 0
    assert score_reach(AccountStat(follower_count=10_000_000)).score == 100  # clamp
    assert "头部" in score_reach(AccountStat(follower_count=200_000)).detail


def test_like_collect_ratio_anchors():
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=150)).score == 75  # 1.5
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=300)).score == 100  # 3.0
    assert score_like_collect_ratio(AccountStat(follower_count=100, total_like_collect=50)).score == 40  # 0.5


def test_ces_weights_comments_higher():
    p = PostStat(likes=10, collects=5, comments=2)
    assert p.ces == 10 + 5 + 2 * 4  # 23


def test_viral_detects_outlier_and_handles_empty():
    posts = [PostStat(likes=100) for _ in range(9)] + [PostStat(likes=1000)]
    dim = score_viral(posts)
    assert abs(dim.metric["hot_rate"] - 0.1) < 0.01  # 1/10 笔记是爆文
    assert dim.metric["ces_median"] == 100
    assert dim.score > 30
    assert score_viral([]).score == 0


def test_activity_frequency_and_recency():
    # 近 90 天里 ~40 篇(约 3.5 篇/周)、最近刚更 → 分高
    fresh = [PostStat(published_at=NOW - timedelta(days=i * 2)) for i in range(40)]
    assert score_activity(fresh, NOW).score >= 60
    # 同样篇数但最后一篇在 100 天前 → recency 惩罚,分低
    stale = [PostStat(published_at=NOW - timedelta(days=100 + i * 7)) for i in range(12)]
    assert score_activity(stale, NOW).score < 40
    # 没有发布时间 → 0
    assert score_activity([PostStat(likes=5)], NOW).score == 0


def test_hard_dimensions_returns_four():
    dims = hard_dimensions(
        AccountStat(follower_count=5000, total_like_collect=12000),
        [PostStat(likes=200, collects=50, comments=10, published_at=NOW - timedelta(days=3))],
        NOW,
    )
    assert [d.key for d in dims] == ["reach", "engagement", "viral", "activity"]
    assert all(0 <= d.score <= 100 for d in dims)


# —— 软实力 / 垂直度(模型判,monkeypatch 掉 LLM)——

def test_judge_vertical_parses(monkeypatch):
    monkeypatch.setattr("app.appraisal.judge.create_json_response",
                        lambda *a, **k: {"score": 90, "niche": "香港保险", "reason": "全是港险科普"})
    dim = judge_vertical(["香港保险攻略", "储蓄险测评"], settings=None)
    assert dim.score == 90 and dim.extra["niche"] == "香港保险"


def test_judge_vertical_fallback_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("llm down")
    monkeypatch.setattr("app.appraisal.judge.create_json_response", boom)
    assert judge_vertical(["x"], settings=None).score == 50


def test_judge_soft_parses_three_dims(monkeypatch):
    canned = {
        "intent_facets": {"题材": "保险", "形态": "科普", "调性": "涨粉IP"},
        "account_facets": {"题材": "保险", "形态": "科普", "调性": "销售"},
        "对路": {"score": 80, "reason": "题材形态匹配,调性偏销售", "题材匹配": True, "形态匹配": True, "调性匹配": False},
        "可学": {"score": 70, "reason": "选题需求驱动"},
        "可蒸馏": {"score": 60, "reason": "代表作够清晰"},
    }
    monkeypatch.setattr("app.appraisal.judge.create_json_response", lambda *a, **k: canned)
    dims = judge_soft("想学把保险讲专业", "标题1\n标题2", settings=None)
    assert dims["fit"].score == 80 and dims["learnable"].score == 70 and dims["distillable"].score == 60
    assert dims["fit"].extra["facet_match"]["调性匹配"] is False


def test_judge_soft_fallback_on_empty_intent():
    dims = judge_soft("", "notes", settings=None)
    assert all(d.score == 50 for d in dims.values())


# —— 编排:_verdict 象限 + _diagnose self 模式 ——

def test_verdict_benchmark_quadrants():
    from app.appraisal import service
    clean = {"has_ban": False, "score": 100, "grade": "干净"}
    ban = {"has_ban": True, "score": 40, "grade": "高危(含封号级违规)"}
    assert service._verdict("benchmark", 80, 80, clean)["level"] == "ok"
    assert service._verdict("benchmark", 80, 80, ban)["level"] == "danger"  # 合规否决
    assert service._verdict("benchmark", 80, 50, clean)["level"] == "warn"
    assert service._verdict("benchmark", 50, 80, clean)["level"] == "warn"
    assert service._verdict("benchmark", 50, 50, clean)["level"] == "muted"


def test_verdict_self_uses_hard_and_compliance():
    from app.appraisal import service
    clean = {"has_ban": False, "score": 100, "grade": "干净"}
    ban = {"has_ban": True, "score": 40, "grade": "高危"}
    assert service._verdict("self", 80, None, clean)["level"] == "ok"
    assert service._verdict("self", 50, None, clean)["level"] == "warn"
    assert service._verdict("self", 80, None, ban)["level"] == "danger"


class _Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_diagnose_self_skips_soft(monkeypatch):
    from app.appraisal import service
    from app.appraisal.judge import JudgedDim
    monkeypatch.setattr(service, "judge_vertical", lambda titles, s, timeout=None: JudgedDim("vertical", "垂直度", 80, "聚焦"))
    monkeypatch.setattr(service, "compliance_scan",
                        lambda *a, **k: {"score": 100, "grade": "干净", "hits": [], "by_severity": {}, "has_ban": False})
    blogger = _Obj(id=1, platform="xhs", follower_count=5000, note_total=50)
    posts = [_Obj(id=i, like_count=200, favorite_count=50, comment_count=10,
                  published_at=NOW, content_type="image", title="港险科普", body_text="正文")
             for i in range(10)]
    rep = service._diagnose(None, blogger, posts, kind="self", intent="", industry=None, db=None, tenant_id=0)
    assert rep["kind"] == "self"
    assert rep["soft"] == [] and rep["soft_score"] is None  # 自己模式无软实力
    assert len(rep["hard"]) == 5  # 4 算 + 垂直度
    assert rep["compliance"]["has_ban"] is False
    assert rep["verdict"]["level"] in {"ok", "warn", "danger"}


# —— 相关性判定 + 对路=相关占比 ——

def test_judge_note_relevance_marks_each(monkeypatch):
    canned = {"items": [{"i": 0, "relevant": True, "reason": ""}, {"i": 1, "relevant": False, "reason": "偏生活"}]}
    monkeypatch.setattr("app.appraisal.judge.create_json_response", lambda *a, **k: canned)
    out = judge_note_relevance("学香港保险", ["港险科普", "今天吃了火锅"], settings=None)
    assert out[0]["relevant"] is True
    assert out[1]["relevant"] is False and "偏生活" in out[1]["reason"]


def test_judge_note_relevance_fallback_all_relevant(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.appraisal.judge.create_json_response", boom)
    out = judge_note_relevance("x", ["a", "b", "c"], settings=None)
    assert len(out) == 3 and all(o["relevant"] for o in out)


def test_judge_note_relevance_empty_intent_all_relevant():
    assert all(o["relevant"] for o in judge_note_relevance("", ["a", "b"], settings=None))


def test_diagnose_benchmark_fit_uses_relevance_ratio(monkeypatch):
    from app.appraisal import service
    from app.appraisal.judge import JudgedDim
    monkeypatch.setattr(service, "judge_vertical", lambda titles, s, timeout=None: JudgedDim("vertical", "垂直度", 80, "聚焦"))
    monkeypatch.setattr(service, "compliance_scan",
                        lambda *a, **k: {"score": 100, "grade": "干净", "hits": [], "by_severity": {}, "has_ban": False})
    monkeypatch.setattr(service, "build_account_content", lambda *a, **k: "brief")
    monkeypatch.setattr(service, "judge_soft", lambda intent, brief, s, timeout=None: {
        "fit": JudgedDim("fit", "对路", 50, "原始理由"),
        "learnable": JudgedDim("learnable", "可学", 70, ""),
        "distillable": JudgedDim("distillable", "可蒸馏", 60, ""),
    })
    blogger = _Obj(id=1, platform="xhs", follower_count=5000, note_total=50)
    posts = [_Obj(id=i, like_count=200, favorite_count=50, comment_count=10,
                  published_at=NOW, content_type="image", title="t", body_text="b") for i in range(10)]
    rep = service._diagnose(None, blogger, posts, kind="benchmark", intent="学保险", industry=None,
                            db=None, tenant_id=0, relevance_ratio=80.0)
    fit = next(d for d in rep["soft"] if d["key"] == "fit")
    assert fit["score"] == 80  # 对路被相关占比覆盖
    assert "80%" in fit["detail"]


# —— 意图引导(suggest_intent):意图够清晰不出题,否则给贴博主的多选题 ——

def test_suggest_intent_clear_skips_questions(monkeypatch):
    monkeypatch.setattr("app.appraisal.intent.create_json_response",
                        lambda *a, **k: {"clear": True, "questions": [{"q": "x", "options": ["a", "b"]}]})
    out = suggest_intent(None, titles=["港险科普"], tags=["保险"], niche="香港保险",
                         intent="想学他把港险讲专业、能涨粉的选题和钩子")
    assert out["clear"] is True and out["questions"] == []


def test_suggest_intent_returns_questions(monkeypatch):
    canned = {"clear": False, "questions": [
        {"q": "你最想学哪方面?", "options": ["选题套路", "涨粉钩子", "口播形式"]},
        {"q": "目标?", "options": ["涨粉", "变现"]},
    ]}
    monkeypatch.setattr("app.appraisal.intent.create_json_response", lambda *a, **k: canned)
    out = suggest_intent(None, titles=["港险科普"], tags=["保险"], niche="香港保险", intent="")
    assert out["clear"] is False
    assert len(out["questions"]) == 2 and out["questions"][0]["options"][0] == "选题套路"


def test_suggest_intent_drops_bad_questions_then_generic(monkeypatch):
    # 选项不足 2 个的题被丢掉;丢空后回落通用题,流程不断。
    monkeypatch.setattr("app.appraisal.intent.create_json_response",
                        lambda *a, **k: {"clear": False, "questions": [{"q": "x", "options": ["只有一个"]}]})
    out = suggest_intent(None, titles=["t"], tags=[], niche="", intent="")
    assert out["clear"] is False and len(out["questions"]) >= 1


def test_suggest_intent_llm_fail_no_intent_gives_generic(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.appraisal.intent.create_json_response", boom)
    out = suggest_intent(None, titles=["t"], tags=[], niche="", intent="")
    assert out["clear"] is False and len(out["questions"]) >= 1


def test_suggest_intent_llm_fail_with_intent_passes(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.appraisal.intent.create_json_response", boom)
    out = suggest_intent(None, titles=["t"], tags=[], niche="", intent="想学他的选题和钩子写法")
    assert out["clear"] is True and out["questions"] == []


def test_suggest_intent_no_content_no_intent_generic():
    # 没素材、也没填意图 → 不调模型,直接通用题。
    out = suggest_intent(None, titles=[], tags=[], niche="", intent="")
    assert out["clear"] is False and len(out["questions"]) >= 1


# —— 自诊断意图(purpose='self'):问的是目标/痛点/阶段,不是「想学什么」——

def test_suggest_intent_self_generic_is_goal_pain_stage():
    # 自诊断兜底题应是「目标/痛点/阶段」那套,而不是对标的「想学什么」。
    out = suggest_intent(None, titles=[], tags=[], niche="", intent="", purpose="self")
    qs = " ".join(q["q"] for q in out["questions"])
    assert out["clear"] is False and len(out["questions"]) >= 1
    assert "达成" in qs or "卡点" in qs or "阶段" in qs
    assert "跟 TA 学" not in qs  # 不是对标的问法


def test_suggest_intent_self_clear_skips(monkeypatch):
    monkeypatch.setattr("app.appraisal.intent.create_json_response",
                        lambda *a, **k: {"clear": True, "questions": []})
    out = suggest_intent(None, titles=["港险科普"], tags=["保险"], niche="香港保险",
                         intent="想把转化做起来,现在有流量没私域留资", purpose="self")
    assert out["clear"] is True and out["questions"] == []


# —— 目标契合(judge_goal_fit,诊断自己用)——

def test_judge_goal_fit_parses(monkeypatch):
    canned = {"score": 72, "grade": "良", "summary": "选题广但转化弱",
              "gaps": ["几乎没有引导留资的钩子", "正文没有 CTA"],
              "actions": ["每篇结尾加一句私域引导", "测评类挂资料领取"]}
    monkeypatch.setattr("app.appraisal.judge.create_json_response", lambda *a, **k: canned)
    out = judge_goal_fit("目标:提升转化;痛点:有流量没留资", "标题1\n标题2", settings=None)
    assert out["score"] == 72 and out["grade"] == "良"
    assert len(out["gaps"]) == 2 and len(out["actions"]) == 2


def test_judge_goal_fit_fallback_empty_intent():
    out = judge_goal_fit("", "notes", settings=None)
    assert out["score"] == 50 and out["gaps"] == [] and out["actions"] == []


def test_judge_goal_fit_fallback_on_error(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.appraisal.judge.create_json_response", boom)
    out = judge_goal_fit("目标:涨粉", "notes", settings=None)
    assert out["score"] == 50 and out["grade"] == "待改进"


def test_diagnose_self_with_intent_adds_goal_fit(monkeypatch):
    from app.appraisal import service
    from app.appraisal.judge import JudgedDim
    monkeypatch.setattr(service, "judge_vertical", lambda titles, s, timeout=None: JudgedDim("vertical", "垂直度", 80, "聚焦"))
    monkeypatch.setattr(service, "compliance_scan",
                        lambda *a, **k: {"score": 100, "grade": "干净", "hits": [], "by_severity": {}, "has_ban": False})
    monkeypatch.setattr(service, "build_account_content", lambda *a, **k: "brief")
    monkeypatch.setattr(service, "judge_goal_fit", lambda intent, brief, s, timeout=None: {
        "score": 65, "grade": "良", "summary": "离转化还差留资动作", "gaps": ["没CTA"], "actions": ["加私域引导"]})
    blogger = _Obj(id=1, platform="xhs", follower_count=5000, note_total=50)
    posts = [_Obj(id=i, like_count=200, favorite_count=50, comment_count=10,
                  published_at=NOW, content_type="image", title="港险科普", body_text="正文") for i in range(10)]
    rep = service._diagnose(None, blogger, posts, kind="self", intent="目标:提升转化", industry=None, db=None, tenant_id=0)
    assert rep["goal_fit"] is not None and rep["goal_fit"]["score"] == 65
    assert rep["soft"] == []  # 自诊断仍无软实力


def test_diagnose_self_without_intent_no_goal_fit(monkeypatch):
    from app.appraisal import service
    from app.appraisal.judge import JudgedDim
    monkeypatch.setattr(service, "judge_vertical", lambda titles, s, timeout=None: JudgedDim("vertical", "垂直度", 80, "聚焦"))
    monkeypatch.setattr(service, "compliance_scan",
                        lambda *a, **k: {"score": 100, "grade": "干净", "hits": [], "by_severity": {}, "has_ban": False})
    blogger = _Obj(id=1, platform="xhs", follower_count=5000, note_total=50)
    posts = [_Obj(id=i, like_count=200, favorite_count=50, comment_count=10,
                  published_at=NOW, content_type="image", title="t", body_text="b") for i in range(10)]
    rep = service._diagnose(None, blogger, posts, kind="self", intent="", industry=None, db=None, tenant_id=0)
    assert rep["goal_fit"] is None  # 没填目标 → 不跑目标契合
