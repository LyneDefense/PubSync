"""证据装配器(evidence.render_stats_digest):预算/优先级/去冗余/分型/去噪/legacy(纯函数,无 LLM)。"""

from app.blogger_distillation.evidence import compliance_watchouts, render_grounding, render_stats_digest


def _digest(hook="", layout="", style="", images=None):
    return {"cover_hook": hook, "layout": layout, "style": style, "images": images or []}


def _sample(*, ext, title, ct="image", like=10000, fav=5000, com=100, body="", transcript="", image_text="", digest=None):
    return {
        "id": 1, "external_id": ext, "title": title, "body_excerpt": body, "content_type": ct,
        "has_transcript": bool(transcript), "transcript_excerpt": transcript,
        "asr_status": "succeeded" if transcript else "skipped",
        "has_image_text": bool(image_text), "image_text_excerpt": image_text,
        "visual_digest": digest or {}, "hashtags": [], "like_count": like, "favorite_count": fav,
        "comment_count": com, "sampled_comment_count": 0, "score": 1.0, "url": "http://x", "top_comments": [],
    }


def _stats(**over):
    base = {
        "sample_count": 20, "average_like": 10000, "average_favorite": 5000, "average_comment": 100,
        "favorite_like_ratio": 0.5, "modality_comparison": "图文均赞高于视频", "subtype_counts": {},
        "title_patterns": {}, "opening_patterns": {}, "cta_patterns": {}, "structure_info": {},
        "transcript_info": {}, "frequent_hashtags": [], "frequency_info": {}, "growth_trend": {},
        "hot_posts": [], "representative_posts": [], "comment_insights_source": [], "opinion_sentences": [],
    }
    base.update(over)
    return base


def test_legacy_bypass_returns_raw_dump():
    out = render_stats_digest(_stats(opinion_sentences=["金句A"]), char_budget=28000, legacy=True)
    assert '"representative_posts"' in out and '"opinion_sentences"' in out  # 旧形态:原始 key 名


def test_account_summary_always_present():
    out = render_stats_digest(_stats(), char_budget=28000)
    assert "【账号概览】" in out and "样本 20 篇" in out


def test_opinion_pool_before_hot_evidence():
    img = _sample(ext="n1", title="爆款一", digest=_digest(hook="钩子", images=[{"index": 1, "role": "封面", "text": "大字", "desc": "讲变现"}]))
    out = render_stats_digest(_stats(opinion_sentences=["我觉得变现的关键是信任"], hot_posts=[img]), char_budget=28000, scope="core")
    assert "观点/金句池" in out and "爆款证据" in out
    assert out.index("观点/金句池") < out.index("爆款证据")  # 金句前置


def test_hot_excluded_from_representative():
    hot = _sample(ext="hot1", title="热门作")
    rep_new = _sample(ext="rep2", title="其它代表作")
    out = render_stats_digest(_stats(hot_posts=[hot], representative_posts=[hot, rep_new]), char_budget=28000)
    assert "补充广度" in out
    rep_section = out.split("补充广度", 1)[1]
    assert "其它代表作" in rep_section and "热门作" not in rep_section  # 代表样本段去掉 hot 冗余


def test_image_block_has_visual_evidence():
    img = _sample(ext="n1", title="图文爆款", ct="image", digest=_digest(
        hook="先照顾好自己", layout="卡片清单",
        images=[{"index": 1, "role": "封面", "text": "变化才是最小单位", "desc": "封面主张"},
                {"index": 2, "role": "清单", "text": "三个信号", "desc": "清单要点"}]))
    out = render_stats_digest(_stats(hot_posts=[img]), char_budget=28000)
    assert "封面钩子：先照顾好自己" in out and "版式:卡片清单" in out
    assert "图内要点" in out and "变化才是最小单位" in out


def test_video_block_has_transcript():
    vid = _sample(ext="v1", title="口播爆款", ct="video", transcript="大家好今天讲变现方法第一步")
    out = render_stats_digest(_stats(hot_posts=[vid]), char_budget=28000)
    assert "口播摘要：" in out and "变现方法" in out


def test_role_filter_skips_noise():
    img = _sample(ext="n1", title="带噪图文", ct="image", digest=_digest(images=[
        {"index": 1, "role": "封面", "text": "干货标题", "desc": "封面"},
        {"index": 2, "role": "实拍", "text": "背景报纸上的无关新闻", "desc": "实拍噪音"}]))
    out = render_stats_digest(_stats(hot_posts=[img]), char_budget=28000)
    assert "干货标题" in out and "背景报纸上的无关新闻" not in out  # 实拍 role 被跳过


def test_desc_missing_falls_back_to_text():
    img = _sample(ext="n1", title="无desc", ct="image", digest=_digest(images=[{"index": 1, "role": "清单", "text": "逐字要点内容", "desc": ""}]))
    out = render_stats_digest(_stats(hot_posts=[img]), char_budget=28000)
    assert "逐字要点内容" in out  # desc 空时回退 text


def test_evidence_block_char_cap():
    images = [{"index": i, "role": "清单", "text": "要点" * 30, "desc": "描述" * 30} for i in range(1, 11)]
    img = _sample(ext="n1", title="多图超长", ct="image", digest=_digest(images=images))
    out = render_stats_digest(_stats(hot_posts=[img]), char_budget=28000)
    block = next(b for b in out.split("\n\n") if "多图超长" in b)
    assert len(block) <= 650  # _BLOCK_CHAR_CAP=600 + 「爆款证据 #1」前缀


def test_opinion_dedup_substring():
    out = render_stats_digest(_stats(opinion_sentences=["核心是信任", "核心是信任关系的建立", "核心是信任"]), char_budget=28000)
    lines = out.splitlines()
    assert "· 核心是信任关系的建立" in lines and "· 核心是信任" not in lines  # 短句被长句吸收


def test_small_budget_keeps_core_drops_tail():
    reps = [_sample(ext=f"r{i}", title=f"代表作品编号{i}", body="正文" * 50) for i in range(40)]
    stats = _stats(opinion_sentences=["我觉得关键在坚持"], hot_posts=[_sample(ext="h1", title="爆款")], representative_posts=reps)
    small = render_stats_digest(stats, char_budget=800, scope="core")
    assert "【账号概览】" in small and "观点/金句池" in small  # 核心必进
    rep_lines = [ln for ln in small.splitlines() if ln.startswith("· 代表作品编号")]
    assert 0 < len(rep_lines) < 40  # 尾部代表样本被预算裁剪


# ============================ 档案信号 grounding ============================

def test_compliance_watchouts_from_groups():
    comp = {
        "violations": [{"category": "绝对化用语", "matched": ["顶级", "最强"]}],
        "advisories": [{"category": "收益承诺", "matched": ["稳赚"]}],
    }
    out = compliance_watchouts(comp)
    assert out[0] == "绝对化用语：顶级、最强" and "收益承诺：稳赚" in out
    assert compliance_watchouts(None) == [] and compliance_watchouts({}) == []


def test_render_grounding_three_sections():
    g = {
        "hot_titles": [{"title": "香港保险vs内地", "like": 12000, "date": "2024-04", "breakout": True}],
        "reader_demand": ["多少钱啊", "适合新手吗"],
        "compliance": {"violations": [{"category": "绝对化用语", "matched": ["顶级"]}]},
    }
    text = render_grounding(g)
    assert "★香港保险vs内地" in text and "1.2w" in text  # 全量真爆文 + 起号★ + 人性化数字
    assert "读者需求" in text and "适合新手吗" in text
    assert "合规红线" in text and "绝对化用语：顶级" in text


def test_render_grounding_empty():
    assert render_grounding(None) == "" and render_grounding({}) == ""
