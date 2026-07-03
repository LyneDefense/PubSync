"""extract_user_profile:小红书 user_info 关键字段的键名锁定(实测键,防回归)。"""

from app.blogger_distillation.search import extract_user_profile


def test_xhs_user_profile_real_keys():
    # 小红书 user_info 实测结构:笔记数=ndiscovery;获赞与收藏=顶层 liked+collected 相加;简介=desc。
    payload = {"data": {"data": {
        "nickname": "阿璐要分析100个博主",
        "desc": "🌱没灵感了，回来看看阿璐笔记",
        "liked": 337430, "collected": 223960,
        "ndiscovery": 324, "follows": 894,
        "collected_notes_num": 0,  # 这是"收藏的笔记"数,不能当作发布数
    }}}
    r = extract_user_profile("xhs", payload)
    assert r["note_total"] == 324
    assert r["liked_collected_count"] == 337430 + 223960
    assert r["signature"].startswith("🌱没灵感了")
    assert r["display_name"] == "阿璐要分析100个博主"


def test_user_profile_missing_counts_are_none():
    # 拿不到就老实留空,不硬编。
    r = extract_user_profile("xhs", {"data": {"data": {"nickname": "x"}}})
    assert r["note_total"] is None and r["liked_collected_count"] is None
