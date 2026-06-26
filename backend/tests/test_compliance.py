from app.compliance import (
    SEVERITY_BAN,
    SEVERITY_THROTTLE,
    build_blocklist,
    compliance_scan,
    compliance_score,
    scan_creation_output,
    scan_l1,
)
from app.compliance.wordlists import CATEGORY_EXTREME, CATEGORY_FINANCE
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


# —— P2 合规引擎(scan_l1 / compliance_scan / 品类红线 / 分级 / 分)——

def test_l1_extreme_word_is_throttle():
    hits = scan_l1(["这是全网第一的好物"], "xhs")
    cats = {h["category"]: h for h in hits}
    assert CATEGORY_EXTREME in cats
    assert cats[CATEGORY_EXTREME]["severity"] == SEVERITY_THROTTLE


def test_l1_diversion_is_ban_level():
    hits = scan_l1(["有需要加微信详聊"], "xhs")
    assert any(h["severity"] == SEVERITY_BAN and "微信" in h["matched"] for h in hits)


def test_finance_redline_only_when_industry_insurance():
    text = ["这款产品保本稳赚,承诺年化收益"]
    assert not any(h["category"] == CATEGORY_FINANCE for h in scan_l1(text, "xhs"))
    fin = [h for h in scan_l1(text, "xhs", industry="香港保险") if h["category"] == CATEGORY_FINANCE]
    assert fin and all(h["severity"] == SEVERITY_BAN for h in fin)


def test_clean_text_scores_100():
    res = compliance_scan(["今天分享一个我自己用着还不错的小方法"], "xhs")
    assert res["score"] == 100 and res["grade"] == "干净" and res["has_ban"] is False


def test_ban_hit_flags_high_risk():
    res = compliance_scan(["保本稳赚,加微信领取"], "xhs", industry="保险")
    assert res["has_ban"] is True and res["grade"].startswith("高危") and res["score"] < 100


def test_score_caps_per_category():
    hits = scan_l1(["最佳最好最强最优最低价最高级"], "xhs")
    assert len([h for h in hits if h["category"] == CATEGORY_EXTREME]) >= 4
    assert compliance_score(hits) >= 60  # 单类封顶 40 → 至少剩 60


def test_scan_creation_output_now_has_severity():
    out = scan_creation_output({"title": "全网第一", "body_text": "加微信"}, "xhs")
    assert out and all({"word", "field", "category", "severity"} <= set(h) for h in out)
