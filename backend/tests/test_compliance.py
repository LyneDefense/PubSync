"""合规组件单测(P1:赛道门控 + 词边界/白名单/上下文 + 两档分级)。

每条关键规则都有正例(该报)+ 反例(白名单/无语境,不该报)。
"""

from app.compliance import detect_verticals, scan_account, scan_creation
from app.xhs_creation.agent.context import CreationContext
from app.xhs_creation.agent.sensors import CreationComplianceSensor


def _ctx(platform="xhs", content_type="text_note", extra=None):
    return CreationContext(
        blogger=None, skill=None, payload=None,
        platform=platform, content_type=content_type, extra_block_words=extra or [],
    )


def _cats(groups):
    return " ".join(g["category"] for g in groups)


# —— 赛道识别 ——

def test_detect_verticals():
    assert "cosmetics" in detect_verticals("护肤美妆")
    assert "finance" in detect_verticals("香港保险")
    assert "maternal" in detect_verticals("", ["母婴", "育儿"])
    assert detect_verticals("旅游美食") == []


# —— 化妆品:合法功效 vs 医疗用语 ——

def test_cosmetic_legal_claim_is_advisory_not_violation():
    # 美白/祛痘 是合法特殊化妆品宣称 → 提示级 advisory,不是封号级违规
    r = scan_account(["主打美白提亮，淡化痘印，修复受损"], "xhs", niche="护肤")
    assert not r.violations
    assert any("功效宣称" in a["category"] for a in r.advisories)


def test_cosmetic_medical_word_is_violation_but_allowlist_ok():
    r = scan_account(["这款能祛皱抗菌，快速换肤"], "xhs", niche="护肤")
    assert any("医疗用语" in v["category"] for v in r.violations)
    # 抗皱/减少皱纹 明确允许 → 不该报
    r2 = scan_account(["主打抗皱，减少细纹和皱纹"], "xhs", niche="护肤")
    assert not any("医疗用语" in v["category"] for v in r2.violations)


# —— 通用:绝对化极限词(口语白名单) ——

def test_extreme_hard_is_violation():
    r = scan_account(["全网第一的好物，销量第一"], "xhs")
    assert any("极限词" in v["category"] for v in r.violations)


def test_extreme_colloquial_suppressed():
    # 「还是最好别…」是口语,不是广告绝对化 → allow_context 抑制
    r = scan_account(["这个点还是最好别熬夜了"], "xhs")
    assert not r.violations and not r.advisories


# —— 平台导流:提到 vs 真导流 ——

def test_platform_mention_not_flagged():
    r = scan_account(["这家民宿在抖音刷到的，亲测好住"], "xhs", niche="旅游")
    assert not r.violations and not r.advisories


def test_platform_diversion_flagged():
    r = scan_account(["同款去淘宝搜XX旗舰店，便宜一半"], "xhs")
    assert any("导流" in v["category"] for v in r.violations)


# —— 疗效宣称:对所有赛道都违规(在通用包) ——

def test_medical_claim_is_universal():
    # 食品号说「治愈」也该报(疾病治疗对所有品类违法)
    r = scan_account(["这个偏方能治愈失眠，还能根治便秘"], "xhs", niche="美食")
    assert r.has_ban and any("疗效" in v["category"] for v in r.violations)


# —— 行业门控:金融红线只在金融赛道 ——

def test_finance_redline_gated_by_vertical():
    # 旅游号说「保本稳赚」→ 金融包未激活,不报
    assert not scan_account(["这个稳赚不赔"], "xhs", niche="旅游").violations
    # 理财号 → 报封号级
    r = scan_account(["这款保本稳赚，承诺年化收益"], "xhs", niche="理财", industry="理财")
    assert any("保证收益" in v["category"] for v in r.violations)
    assert r.has_ban


# —— 诊断精确度:护肤号不再一堆封号级误报 ——

def test_diagnosis_skincare_precision():
    beauty = [
        "这支精华我用下来最好还是晚上涂，主打美白提亮",
        "在抖音刷到的手法，搬到小红书复刻",
        "顶级好用的唇泥，独家色号",
        "换季祛痘 + 淡化痘印，修复受损屏障",
        "评论区免费领取小样",
    ]
    r = scan_account(beauty, "xhs", niche="护肤美妆")
    assert r.violations == []      # 无封号级误报
    assert r.score == 100
    assert r.verticals == ["cosmetics"]


# —— 覆盖率:命中占比 ——

def test_coverage_counts_notes():
    r = scan_account(["全网第一好物", "全网第一推荐", "普通内容"], "xhs")
    grp = next(v for v in r.violations if "极限词" in v["category"])
    assert grp["coverage"] == {"hit_notes": 2, "total_notes": 3}


# —— 算分 & 干净 ——

def test_clean_scores_100():
    r = scan_account(["今天分享一个我自己用着还不错的小方法"], "xhs")
    assert r.score == 100 and r.grade == "干净" and not r.has_ban


def test_ban_flags_high_risk():
    r = scan_account(["保本稳赚，加微信领取"], "xhs", niche="保险", industry="保险")
    assert r.has_ban and r.grade.startswith("高危") and r.score < 100


# —— 创作闸门:拦真违规,不拦合法功效 ——

def test_creation_blocks_violations_not_legal_claims():
    d = scan_creation(
        {"title": "全网第一", "body_text": "加微信领取，主打美白", "hashtags": ["秒杀"]},
        "xhs", niche="护肤",
    ).creation_dict()
    assert d["passed"] is False
    words = {h["word"] for h in d["hits"]}
    assert "全网第一" in words and "加微信" in words and "秒杀" in words
    assert "美白" not in words  # 合法功效不拦


def test_creation_hits_have_shape():
    d = scan_creation({"title": "全网第一", "body_text": "加微信"}, "xhs").creation_dict()
    assert d["hits"] and all({"word", "field", "category", "severity", "hint"} <= set(h) for h in d["hits"])


def test_creation_sensor_blocks_dirty_passes_clean():
    sensor = CreationComplianceSensor()
    dirty = sensor.check({"title": "全网第一神器", "body_text": "加微信治愈一切", "hashtags": [], "cover_text": "", "script": {}}, _ctx())
    assert dirty.passed is False and dirty.issues and dirty.corrective_feedback
    clean = sensor.check({"title": "我的护肤小记", "body_text": "用着挺舒服", "hashtags": ["护肤"], "cover_text": "", "script": {}}, _ctx())
    assert clean.passed is True


def test_scan_scripts_voiceover():
    d = scan_creation(
        {"title": "正常", "body_text": "正常", "hashtags": [],
         "script": {"segments": [{"voiceover": "这是全网第一好物", "subtitle": "快来秒杀"}]}},
        "douyin",
    ).creation_dict()
    assert {"全网第一", "秒杀"} <= {h["word"] for h in d["hits"]}


# —— 自定义扩展词 ——

def test_extra_words_flagged():
    r = scan_account(["内含某自定义敏感词"], "xhs", extra_words=["自定义敏感词"])
    assert any("自定义" in v["category"] for v in r.violations)
