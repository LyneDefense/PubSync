from app.compliance import build_blocklist, scan_creation_output
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.sensors import CreationComplianceSensor


def _ctx(platform="xhs", content_type="text_note", extra=None):
    # sensor 只用到 platform / content_type / extra_block_words,其余给占位即可。
    return CreationContext(
        blogger=None,
        skill=None,
        payload=None,
        platform=platform,
        content_type=content_type,
        extra_block_words=extra or [],
    )


def test_blocklist_has_common_and_platform_words():
    bl = build_blocklist("xhs")
    assert bl["极限词"] and bl["医疗功效"] and bl["诱导营销"]
    assert "淘宝" in bl["竞品外链"]  # 平台特定


def test_scan_flags_words_with_category_and_field():
    result = {
        "title": "全网第一的好物",
        "body_text": "用了能治愈痘痘,加微信领取",
        "hashtags": ["秒杀"],
        "cover_text": "",
        "script": {},
    }
    hits = scan_creation_output(result, "xhs")
    words = {h["word"] for h in hits}
    assert "全网第一" in words and "治愈" in words and "加微信" in words and "秒杀" in words
    # 子串去重:同字段里「加微」「微信」被更长的「加微信」吸收。
    assert "加微" not in words
    cats = {h["category"] for h in hits}
    assert "极限词" in cats and "医疗功效" in cats and "诱导营销" in cats
    # 每个命中都带字段定位。
    assert all(h["field"] for h in hits)


def test_scan_clean_text_no_hits():
    result = {
        "title": "我最近的护肤心得",
        "body_text": "分享几个用着舒服的小物,欢迎评论区一起聊聊",
        "hashtags": ["护肤", "日常"],
        "cover_text": "护肤小记",
        "script": {},
    }
    assert scan_creation_output(result, "xhs") == []


def test_compliance_sensor_blocks_dirty_and_passes_clean():
    sensor = CreationComplianceSensor()
    dirty = sensor.check({"title": "最好用的神器", "body_text": "治愈一切", "hashtags": [], "cover_text": "", "script": {}}, _ctx())
    assert dirty.passed is False
    assert dirty.issues and dirty.corrective_feedback
    clean = sensor.check({"title": "我的护肤小记", "body_text": "用着挺舒服", "hashtags": ["护肤"], "cover_text": "", "script": {}}, _ctx())
    assert clean.passed is True


def test_scan_respects_extra_block_words():
    result = {"title": "内含某自定义敏感词", "body_text": "", "hashtags": [], "cover_text": "", "script": {}}
    hits = scan_creation_output(result, "xhs", extra_words=["自定义敏感词"])
    assert any(h["word"] == "自定义敏感词" and h["category"] == "自定义" for h in hits)


def test_scan_scripts_voiceover():
    result = {
        "title": "正常标题",
        "body_text": "正常正文",
        "hashtags": [],
        "cover_text": "",
        "script": {"segments": [{"voiceover": "这是全网第一好物", "subtitle": "快来秒杀"}]},
    }
    hits = scan_creation_output(result, "douyin")
    words = {h["word"] for h in hits}
    assert "全网第一" in words and "秒杀" in words
