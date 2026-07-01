"""智能选材·rank_notes_by_need 单测。"""

from app.blogger_distillation.note_ranking import rank_notes_by_need

NOTES = [
    {"id": 11, "title": "港险储蓄分红险测评", "subtype": "image"},
    {"id": 22, "title": "今天喝了杯咖啡", "subtype": "image"},
    {"id": 33, "title": "重疾险怎么选不踩坑", "subtype": "video"},
]


def test_ranks_maps_ids_and_sorts(monkeypatch):
    canned = {"name": "港险干货精选", "items": [
        {"i": 0, "score": 90, "reason": "储蓄险干货"},
        {"i": 1, "score": 10, "reason": "生活流水"},
        {"i": 2, "score": 80, "reason": "重疾险选购"},
    ]}
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", lambda *a, **k: canned)
    out = rank_notes_by_need("我想学怎么讲保险产品", NOTES, settings=None)
    assert out["name"] == "港险干货精选"
    # 覆盖全部 + 按分降序
    assert [it["post_id"] for it in out["items"]] == [11, 33, 22]
    assert out["items"][0]["score"] == 90 and out["items"][0]["reason"] == "储蓄险干货"


def test_missing_items_get_zero(monkeypatch):
    # 模型只评了一条 → 其余补 0 分,仍覆盖全部。
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"name": "x", "items": [{"i": 2, "score": 70, "reason": "r"}]})
    out = rank_notes_by_need("保险", NOTES, settings=None)
    assert len(out["items"]) == 3
    assert out["items"][0]["post_id"] == 33 and out["items"][0]["score"] == 70
    assert {it["post_id"] for it in out["items"] if it["score"] == 0} == {11, 22}


def test_score_clamped(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"name": "n", "items": [{"i": 0, "score": 999}, {"i": 1, "score": -5}]})
    out = rank_notes_by_need("x", NOTES, settings=None)
    scores = {it["post_id"]: it["score"] for it in out["items"]}
    assert scores[11] == 100 and scores[22] == 0


def test_empty_need_returns_empty():
    assert rank_notes_by_need("", NOTES, settings=None) == {"name": "", "items": []}


def test_no_notes_returns_empty():
    assert rank_notes_by_need("保险", [], settings=None) == {"name": "", "items": []}


def test_llm_failure_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", boom)
    assert rank_notes_by_need("保险", NOTES, settings=None) == {"name": "", "items": []}
