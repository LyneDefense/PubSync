from app.blogger_distillation.search import fans_from_text, looks_like_user, normalize_user


def test_looks_like_user_excludes_filter_items():
    # 粉丝区间筛选项(All/0-100/...)有 id+name 但不是用户,应被排除。
    filt = {"id": "all", "name": "All", "sub_filters": None, "need_location_info": False, "icon_url": ""}
    assert looks_like_user(filt) is False
    user = {"id": "631", "name": "李子做美食", "image": "http://a", "sub_title": "Fans 160.8k", "link": "x"}
    assert looks_like_user(user) is True


def test_fans_from_text():
    assert fans_from_text("Fans 160.8k") == 160800
    assert fans_from_text("粉丝 16.5万") == 165000
    assert fans_from_text("Fans 2.1m") == 2_100_000
    assert fans_from_text("1.2亿") == 120_000_000
    assert fans_from_text("") == 0
    assert fans_from_text("Fans") == 0


def test_normalize_user_xhs_parses_fans_from_sub_title():
    item = {
        "id": "63171542000000001902c760",
        "name": "李子做美食",
        "image": "http://avatar",
        "desc": "RED ID: 7680400ww",
        "sub_title": "Fans 160.8k",
    }
    result = normalize_user("xhs", item)
    assert result is not None
    assert result.follower_count == 160800
    assert result.display_name == "李子做美食"
    assert result.homepage_url.endswith("63171542000000001902c760")
