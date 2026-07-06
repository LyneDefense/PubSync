"""对标分析·我 vs TA 差距(gap):B 事实差(规则)+ A 打法 diff(monkeypatch LLM)。"""

from dataclasses import dataclass
from datetime import datetime

from app.appraisal import gap as gap_mod
from app.appraisal.gap import build_gap
from app.models.common import utc_now


@dataclass
class _Blogger:
    id: int = 1
    display_name: str = "号"
    follower_count: int = 0


@dataclass
class _Post:
    like_count: int = 0
    favorite_count: int = 0
    published_at: datetime | None = None


def _recent(n: int, like: int = 100) -> list:
    now = utc_now()
    return [_Post(like_count=like, favorite_count=0, published_at=now) for _ in range(n)]


def test_fact_diff_and_no_playbook_without_skill():
    mine = _Blogger(id=1, display_name="我", follower_count=5000)
    ta = _Blogger(id=2, display_name="TA", follower_count=50000)
    g = build_gap(None, mine, ta, _recent(2), _recent(8, like=500), mine_skill_md="", ta_skill_md="", intent="", timeout=10)
    facts = g["facts"]
    assert len(facts) == 3
    reach = next(f for f in facts if "体量" in f["aspect"])
    assert reach["me"] == "5000" and reach["ta"] == "5w" and "落后" in reach["gap"]  # 5000 < 50000
    assert g["playbook"] is None and g["note"]  # 缺画像 → 无 diff + 提示


def test_playbook_diff_when_both_distilled(monkeypatch):
    monkeypatch.setattr(gap_mod, "create_json_response", lambda *a, **k: {
        "items": [{"aspect": "标题", "ta": "数字型", "me": "平铺", "gap": "缺钩子,补数字"}],
        "summary": "标题钩子弱",
    })
    g = build_gap(None, _Blogger(1, "我", 1000), _Blogger(2, "TA", 1000), _recent(1), _recent(1),
                  mine_skill_md="我的打法…", ta_skill_md="TA的打法…", intent="涨粉", timeout=10)
    assert g["note"] is None
    assert g["playbook"]["items"][0]["aspect"] == "标题" and g["playbook"]["summary"] == "标题钩子弱"


def test_playbook_diff_llm_fail_degrades(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(gap_mod, "create_json_response", boom)
    g = build_gap(None, _Blogger(1), _Blogger(2), _recent(1), _recent(1),
                  mine_skill_md="x", ta_skill_md="y", intent="", timeout=10)
    assert g["playbook"] is None  # 失败降级,不抛
