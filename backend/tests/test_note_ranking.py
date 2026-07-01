"""智能选材·rank_notes_by_need 单测(score-only 紧凑输出 + 分批并行 + 失败重试 + 有界降级)。"""

from app.blogger_distillation.note_ranking import rank_notes_by_need

NOTES = [
    {"id": 11, "title": "港险储蓄分红险测评", "subtype": "image"},
    {"id": 22, "title": "今天喝了杯咖啡", "subtype": "image"},
    {"id": 33, "title": "重疾险怎么选不踩坑", "subtype": "video"},
]


def test_ranks_maps_ids_and_sorts(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"s": [{"i": 0, "v": 90}, {"i": 1, "v": 10}, {"i": 2, "v": 80}]})
    out = rank_notes_by_need("我想学怎么讲保险", NOTES, settings=None)
    assert out["name"] == "我想学怎么讲保险"  # 名字由需求派生
    assert [it["post_id"] for it in out["items"]] == [11, 33, 22]  # 覆盖全部 + 按分降序
    assert out["items"][0]["score"] == 90


def test_name_truncated_for_long_need(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"s": [{"i": 0, "v": 50}]})
    out = rank_notes_by_need("这是一个非常非常非常非常长的需求描述超过十四字", NOTES, settings=None)
    assert out["name"].endswith("…") and len(out["name"]) == 15


def test_missing_items_get_zero(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"s": [{"i": 2, "v": 70}]})
    out = rank_notes_by_need("保险", NOTES, settings=None)
    assert len(out["items"]) == 3
    assert out["items"][0]["post_id"] == 33 and out["items"][0]["score"] == 70
    assert {it["post_id"] for it in out["items"] if it["score"] == 0} == {11, 22}


def test_score_clamped(monkeypatch):
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"s": [{"i": 0, "v": 999}, {"i": 1, "v": -5}]})
    scores = {it["post_id"]: it["score"] for it in rank_notes_by_need("x", NOTES, settings=None)["items"]}
    assert scores[11] == 100 and scores[22] == 0


def test_batches_and_maps_offsets(monkeypatch):
    # 65 篇 → 3 批(30/30/5)。每批「批内第 0 条」给 90;验证跨批 offset 映射。
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response",
                        lambda *a, **k: {"s": [{"i": 0, "v": 90}]})
    notes = [{"id": i, "title": f"t{i}", "subtype": "image"} for i in range(65)]
    by = {it["post_id"]: it["score"] for it in rank_notes_by_need("x", notes, settings=None)["items"]}
    assert by[0] == 90 and by[30] == 90 and by[60] == 90


def test_retry_recovers_transient_failure(monkeypatch):
    # 含 t30 的批第一次超时、重试成功 → 该批笔记被救回,而非默认 0。
    calls = {"t30": 0}

    def fake(settings, prompt, timeout=None):
        if "t30" in prompt:
            calls["t30"] += 1
            if calls["t30"] == 1:
                raise RuntimeError("read timeout")
        return {"s": [{"i": 0, "v": 77}]}
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", fake)
    notes = [{"id": i, "title": f"t{i}", "subtype": "image"} for i in range(60)]
    by = {it["post_id"]: it["score"] for it in rank_notes_by_need("x", notes, settings=None)["items"]}
    assert by[30] == 77 and calls["t30"] == 2  # 重试跑了第二次并救回


def test_persistent_batch_failure_bounded(monkeypatch):
    # 含 t30 的批两次都失败 → 只该批默认 0,其余不受影响。
    def fake(settings, prompt, timeout=None):
        if "t30" in prompt:
            raise RuntimeError("read timeout")
        return {"s": [{"i": 0, "v": 88}]}
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", fake)
    notes = [{"id": i, "title": f"t{i}", "subtype": "image"} for i in range(60)]
    by = {it["post_id"]: it["score"] for it in rank_notes_by_need("x", notes, settings=None)["items"]}
    assert by[0] == 88 and by[30] == 0 and len(by) == 60


def test_empty_need_returns_empty():
    assert rank_notes_by_need("", NOTES, settings=None) == {"name": "", "items": []}


def test_no_notes_returns_empty():
    assert rank_notes_by_need("保险", [], settings=None) == {"name": "", "items": []}


def test_all_batches_fail_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr("app.blogger_distillation.note_ranking.create_json_response", boom)
    assert rank_notes_by_need("保险", NOTES, settings=None) == {"name": "", "items": []}
