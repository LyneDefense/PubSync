"""智能选材·rank_notes_by_need 单测(分批 + 并行 + 有界降级)。"""

from app.blogger_distillation.note_ranking import rank_notes_by_need

NOTES = [
    {"id": 11, "title": "港险储蓄分红险测评", "subtype": "image"},
    {"id": 22, "title": "今天喝了杯咖啡", "subtype": "image"},
    {"id": 33, "title": "重疾险怎么选不踩坑", "subtype": "video"},
]


def test_ranks_maps_ids_and_sorts(monkeypatch):
    canned = {"items": [
        {"i": 0, "score": 90, "reason": "储蓄险干货"},
        {"i": 1, "score": 10, "reason": "生活流水"},
        {"i": 2, "score": 80, "reason": "重疾险选购"},
    ]}
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", lambda *a, **k: canned)
    out = rank_notes_by_need("我想学怎么讲保险", NOTES, settings=None)
    assert out["name"] == "我想学怎么讲保险"  # 名字由需求派生(≤14 字不截断)
    assert [it["post_id"] for it in out["items"]] == [11, 33, 22]  # 覆盖全部 + 按分降序
    assert out["items"][0]["score"] == 90 and out["items"][0]["reason"] == "储蓄险干货"


def test_name_truncated_for_long_need(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"items": [{"i": 0, "score": 50}]})
    out = rank_notes_by_need("这是一个非常非常非常非常长的需求描述超过十四字", NOTES, settings=None)
    assert out["name"].endswith("…") and len(out["name"]) == 15


def test_missing_items_get_zero(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"items": [{"i": 2, "score": 70, "reason": "r"}]})
    out = rank_notes_by_need("保险", NOTES, settings=None)
    assert len(out["items"]) == 3
    assert out["items"][0]["post_id"] == 33 and out["items"][0]["score"] == 70
    assert {it["post_id"] for it in out["items"] if it["score"] == 0} == {11, 22}


def test_score_clamped(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"items": [{"i": 0, "score": 999}, {"i": 1, "score": -5}]})
    out = rank_notes_by_need("x", NOTES, settings=None)
    scores = {it["post_id"]: it["score"] for it in out["items"]}
    assert scores[11] == 100 and scores[22] == 0


def test_batches_and_maps_offsets(monkeypatch):
    # 65 篇 → 3 批(30/30/5)。每批「批内第 0 条」给 90;验证跨批的 offset 映射正确。
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"items": [{"i": 0, "score": 90, "reason": "r"}]})
    notes = [{"id": i, "title": f"t{i}", "subtype": "image"} for i in range(65)]
    out = rank_notes_by_need("x", notes, settings=None)
    by = {it["post_id"]: it["score"] for it in out["items"]}
    assert by[0] == 90 and by[30] == 90 and by[60] == 90  # 各批批内第 0 条 = 全局 0/30/60
    assert len(out["items"]) == 65


def test_partial_batch_failure_keeps_rest(monkeypatch):
    # 第二批(含 t30)超时失败,第一批成功 → 不再全军覆没:第一批仍有分。
    def fake(settings, prompt, timeout=None):
        if "t30" in prompt:
            raise RuntimeError("read timeout")
        return {"items": [{"i": 0, "score": 88, "reason": "r"}]}
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", fake)
    notes = [{"id": i, "title": f"t{i}", "subtype": "image"} for i in range(60)]
    out = rank_notes_by_need("x", notes, settings=None)
    by = {it["post_id"]: it["score"] for it in out["items"]}
    assert by[0] == 88 and by[30] == 0 and len(out["items"]) == 60


def test_empty_need_returns_empty():
    assert rank_notes_by_need("", NOTES, settings=None) == {"name": "", "items": []}


def test_no_notes_returns_empty():
    assert rank_notes_by_need("保险", [], settings=None) == {"name": "", "items": []}


def test_all_batches_fail_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", boom)
    assert rank_notes_by_need("保险", NOTES, settings=None) == {"name": "", "items": []}
