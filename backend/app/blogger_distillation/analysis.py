from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from app.blogger_distillation.modality import coarse_modality
from app.blogger_distillation.post_content import visual_digest_dict
from app.models import BloggerPost


TITLE_PATTERNS: dict[str, str] = {
    "数字型": r"\d+|一|二|三|四|五|六|七|八|九|十|几个|种|条|招",
    "疑问型": r"[?？]|为什么|怎么办|是不是|如何|怎么",
    "教程型": r"教程|攻略|指南|手把手|保姆级|方法|步骤",
    "列表型": r"清单|合集|盘点|TOP|推荐|必备",
    "对比型": r"对比|区别|测评|横评|优缺点|值不值",
    "故事型": r"我|我的|亲测|经历|复盘|记录",
    "悬念型": r"真相|秘密|没想到|原来|竟然|居然",
    "避坑型": r"别|不要|千万|踩坑|避坑|不建议|后悔",
    "人群定位型": r"新手|第一次|养猫人|养狗人|铲屎官|宝妈|打工人|学生党",
}

CTA_PATTERNS: dict[str, str] = {
    "收藏引导": r"收藏|码住|保存|留着",
    "关注引导": r"关注|蹲后续",
    "评论引导": r"评论|留言|你觉得|你们|有没有",
    "私信引导": r"私信|后台|发我",
    "点赞引导": r"点赞|点个赞",
    "转发引导": r"转发|分享给",
}

OPENING_PATTERNS: dict[str, str] = {
    "问题开头": r"^(为什么|怎么|如何|你有没有|是不是|难道)",
    "观点直抛": r"^(其实|说实话|我发现|真正|最重要)",
    "故事开头": r"^(我|昨天|最近|前几天|第一次)",
    "痛点开头": r"(烦|焦虑|后悔|踩坑|崩溃|麻烦|不会)",
    "数据开头": r"^\d+|^一|^二|^三",
}


def _percentile_within_modality(posts: list[BloggerPost]) -> dict[int, float]:
    """每条 post 在「同模态(图文/视频)」内按 score 的百分位(1.0=同模态最高)。
    用它排爆款,避免量级大的模态(常是某一类)垄断 TOP。"""
    groups: dict[str, list[BloggerPost]] = defaultdict(list)
    for post in posts:
        groups[coarse_modality(post.content_type)].append(post)
    pct: dict[int, float] = {}
    for items in groups.values():
        ordered = sorted(items, key=lambda item: item.score)
        n = len(ordered)
        for rank, post in enumerate(ordered):
            pct[id(post)] = (rank + 1) / n if n else 0.0
    return pct


def analyze_by_modality(posts: list[BloggerPost]) -> dict[str, dict[str, Any]]:
    """按粗模态(image/video)分别算互动:均赞/均藏、藏赞比、爆款基线。"""
    groups: dict[str, list[BloggerPost]] = defaultdict(list)
    for post in posts:
        groups[coarse_modality(post.content_type)].append(post)
    result: dict[str, dict[str, Any]] = {}
    for modality, items in groups.items():
        n = len(items)
        total_like = sum(item.like_count for item in items)
        avg_like = total_like / max(n, 1)
        result[modality] = {
            "count": n,
            "average_like": round(avg_like, 2),
            "average_favorite": round(sum(item.favorite_count for item in items) / max(n, 1), 2),
            "favorite_like_ratio": round(sum(item.favorite_count for item in items) / max(total_like, 1), 4),
            "hot_threshold_3x": round(avg_like * 3, 1),
        }
    return result


def modality_comparison(by_modality: dict[str, dict[str, Any]]) -> str:
    """一句话:视频 vs 图文 表现对比(仅两类都有时)。"""
    image = by_modality.get("image")
    video = by_modality.get("video")
    if not image or not video:
        return ""
    iv = image["average_like"]
    vv = video["average_like"]
    if vv > iv * 1.5:
        return f"视频均赞 {vv:,.0f} 显著高于图文 {iv:,.0f}"
    if iv > vv * 1.5:
        return f"图文均赞 {iv:,.0f} 显著高于视频 {vv:,.0f}"
    return f"视频均赞 {vv:,.0f}、图文均赞 {iv:,.0f},两种形式基本持平"


def analyze_posts(posts: list[BloggerPost]) -> dict[str, Any]:
    # 爆款排序在「模态内」做:先按同模态百分位,再按绝对分数兜底。
    within_pct = _percentile_within_modality(posts)
    sorted_posts = sorted(posts, key=lambda item: (within_pct.get(id(item), 0.0), item.score), reverse=True)
    hot_count = min(10, max(3, int(len(sorted_posts) * 0.2))) if sorted_posts else 0
    hot_posts = sorted_posts[:hot_count]
    by_modality = analyze_by_modality(posts)
    comments = collect_comments(posts)
    category_stats = classify_posts(posts)
    frequency_info = analyze_posting_frequency(posts)
    structure_info = analyze_body_structure(posts)
    transcript_info = analyze_transcript_structure(posts)
    title_patterns = detect_title_patterns(posts)
    cta_patterns = detect_text_patterns(posts, CTA_PATTERNS, body=True)
    opening_patterns = detect_opening_patterns(posts)
    transcript_opening_patterns = detect_transcript_opening_patterns(posts)
    emoji_info = analyze_emoji_usage(posts)
    trend_info = analyze_growth_trend(posts)
    hot_post_summaries = [post_summary(item) for item in hot_posts]
    return {
        "sample_count": len(posts),
        "comment_total": len(comments),
        "average_like": round(sum(item.like_count for item in posts) / max(len(posts), 1), 2),
        "average_favorite": round(sum(item.favorite_count for item in posts) / max(len(posts), 1), 2),
        "average_comment": round(sum(item.comment_count for item in posts) / max(len(posts), 1), 2),
        "favorite_like_ratio": round(sum(item.favorite_count for item in posts) / max(sum(item.like_count for item in posts), 1), 4),
        "by_modality": by_modality,
        "modality_comparison": modality_comparison(by_modality),
        "subtype_counts": dict(Counter(post.content_subtype for post in posts)),
        "title_patterns": title_patterns,
        "opening_patterns": opening_patterns,
        "cta_patterns": cta_patterns,
        "structure_info": structure_info,
        "transcript_info": transcript_info,
        "emoji_info": emoji_info,
        "transcript_opening_patterns": transcript_opening_patterns,
        "frequent_hashtags": frequent_hashtags(posts),
        "category_stats": category_stats,
        "frequency_info": frequency_info,
        "growth_trend": trend_info,
        "hot_posts": hot_post_summaries,
        "representative_posts": [post_summary(item) for item in sorted_posts[: min(20, len(sorted_posts))]],
        "comment_insights_source": comments[:100],
        "opinion_sentences": extract_opinion_sentences(posts)[:80],
    }


def detect_title_patterns(posts: list[BloggerPost]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {key: {"count": 0, "examples": []} for key in TITLE_PATTERNS}
    for post in posts:
        for name, pattern in TITLE_PATTERNS.items():
            if re.search(pattern, post.title, re.IGNORECASE):
                result[name]["count"] += 1
                if len(result[name]["examples"]) < 3:
                    result[name]["examples"].append(post.title)
    return with_pct(result, len(posts))


def detect_text_patterns(posts: list[BloggerPost], patterns: dict[str, str], *, body: bool = False) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {key: {"count": 0, "examples": []} for key in patterns}
    for post in posts:
        text = f"{post.title}\n{post.body_text}" if body else post.title
        for name, pattern in patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                result[name]["count"] += 1
                if len(result[name]["examples"]) < 3:
                    result[name]["examples"].append(post.title)
    return with_pct(result, len(posts))


def detect_opening_patterns(posts: list[BloggerPost]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {key: {"count": 0, "examples": []} for key in OPENING_PATTERNS}
    for post in posts:
        opening = post.body_text.strip()[:120] or post.title
        for name, pattern in OPENING_PATTERNS.items():
            if re.search(pattern, opening, re.IGNORECASE):
                result[name]["count"] += 1
                if len(result[name]["examples"]) < 3:
                    result[name]["examples"].append(opening[:80])
    return with_pct(result, len(posts))


def detect_transcript_opening_patterns(posts: list[BloggerPost]) -> dict[str, dict[str, Any]]:
    transcript_posts = [post for post in posts if (post.transcript_text or "").strip()]
    result: dict[str, dict[str, Any]] = {key: {"count": 0, "examples": []} for key in OPENING_PATTERNS}
    for post in transcript_posts:
        opening = post.transcript_text.strip()[:120]
        for name, pattern in OPENING_PATTERNS.items():
            if re.search(pattern, opening, re.IGNORECASE):
                result[name]["count"] += 1
                if len(result[name]["examples"]) < 3:
                    result[name]["examples"].append(opening[:80])
    return with_pct(result, len(transcript_posts))


def with_pct(result: dict[str, dict[str, Any]], total: int) -> dict[str, dict[str, Any]]:
    for data in result.values():
        data["pct"] = round(data["count"] / max(total, 1) * 100, 1)
    return result


def analyze_body_structure(posts: list[BloggerPost]) -> dict[str, Any]:
    lengths = [len(item.body_text or "") for item in posts]
    list_count = sum(1 for item in posts if re.search(r"(^|\n)\s*[-*•]|\d+[.、)]", item.body_text or ""))
    number_heading_count = sum(1 for item in posts if re.search(r"(^|\n)\s*(\d+|一|二|三|四|五)[.、]", item.body_text or ""))
    return {
        "avg_length": round(sum(lengths) / max(len(lengths), 1), 1),
        "short_count": sum(1 for value in lengths if value < 200),
        "medium_count": sum(1 for value in lengths if 200 <= value <= 500),
        "long_count": sum(1 for value in lengths if value > 500),
        "list_format_count": list_count,
        "number_heading_count": number_heading_count,
    }


def analyze_transcript_structure(posts: list[BloggerPost]) -> dict[str, Any]:
    video_posts = [item for item in posts if item.content_type == "video"]
    transcript_posts = [item for item in video_posts if (item.transcript_text or "").strip()]
    lengths = [len(item.transcript_text or "") for item in transcript_posts]
    subtitle_count = sum(1 for item in transcript_posts if item.asr_status == "subtitle")
    asr_count = sum(1 for item in transcript_posts if item.asr_status == "succeeded")
    skipped_count = sum(1 for item in video_posts if item.asr_status in {"skipped", "failed", "pending"})
    opening_examples = [item.transcript_text.strip()[:120] for item in transcript_posts[:5] if item.transcript_text.strip()]
    ending_examples = [item.transcript_text.strip()[-120:] for item in transcript_posts[:5] if item.transcript_text.strip()]
    return {
        "video_count": len(video_posts),
        "transcript_count": len(transcript_posts),
        "subtitle_count": subtitle_count,
        "asr_count": asr_count,
        "skipped_count": skipped_count,
        "avg_transcript_length": round(sum(lengths) / max(len(lengths), 1), 1),
        "short_transcript_count": sum(1 for value in lengths if value < 500),
        "medium_transcript_count": sum(1 for value in lengths if 500 <= value <= 2000),
        "long_transcript_count": sum(1 for value in lengths if value > 2000),
        "opening_examples": opening_examples,
        "ending_examples": ending_examples,
        "note": "以上长度只代表视频字幕/口播转写，不代表图文正文长度。",
    }


def analyze_emoji_usage(posts: list[BloggerPost]) -> dict[str, Any]:
    emoji_counter: Counter[str] = Counter()
    posts_with_emoji = 0
    for post in posts:
        emojis = re.findall(r"[\U0001F300-\U0001FAFF]", f"{post.title}\n{post.body_text}")
        if emojis:
            posts_with_emoji += 1
            emoji_counter.update(emojis)
    return {
        "posts_with_emoji": posts_with_emoji,
        "emoji_usage_pct": round(posts_with_emoji / max(len(posts), 1) * 100, 1),
        "top_emojis": [{"emoji": emoji, "count": count} for emoji, count in emoji_counter.most_common(10)],
    }


def classify_posts(posts: list[BloggerPost]) -> dict[str, Any]:
    categories = {
        "教程/实操": r"教程|攻略|方法|步骤|怎么|如何|指南|手把手",
        "测评/推荐": r"测评|推荐|好物|清单|横评|对比|值不值",
        "经验分享": r"经验|亲测|复盘|踩坑|避坑|后悔|第一次",
        "知识科普": r"知识|科普|原因|为什么|原理|真相",
        "日常记录": r"日常|记录|vlog|plog|今天|最近",
    }
    buckets: dict[str, list[BloggerPost]] = defaultdict(list)
    for post in posts:
        text = f"{post.title}\n{post.body_text}"
        matched = "其他"
        for name, pattern in categories.items():
            if re.search(pattern, text, re.IGNORECASE):
                matched = name
                break
        buckets[matched].append(post)
    result = {}
    for name, items in buckets.items():
        top = max(items, key=lambda item: item.score)
        result[name] = {
            "count": len(items),
            "pct": round(len(items) / max(len(posts), 1) * 100, 1),
            "avg_like": round(sum(item.like_count for item in items) / max(len(items), 1), 1),
            "top_post": top.title,
        }
    return result


def analyze_posting_frequency(posts: list[BloggerPost]) -> dict[str, Any]:
    dates = sorted([item.published_at for item in posts if item.published_at is not None])
    if len(dates) < 2:
        return {"pattern": "时间数据不足", "avg_days_between": None}
    intervals = []
    for index in range(1, len(dates)):
        intervals.append(max((dates[index] - dates[index - 1]).total_seconds() / 86400, 0))
    avg_days = round(sum(intervals) / max(len(intervals), 1), 1)
    if avg_days <= 1.5:
        pattern = "高频日更"
    elif avg_days <= 4:
        pattern = "稳定周更多次"
    elif avg_days <= 10:
        pattern = "低频但持续"
    else:
        pattern = "更新间隔较长"
    return {"pattern": pattern, "avg_days_between": avg_days}


def analyze_growth_trend(posts: list[BloggerPost]) -> dict[str, Any]:
    dated = sorted([item for item in posts if item.published_at is not None], key=lambda item: item.published_at or datetime.min)
    if len(dated) < 8:
        return {"summary": "样本或时间数据不足，暂不判断趋势"}
    midpoint = len(dated) // 2
    early = dated[:midpoint]
    recent = dated[midpoint:]
    early_avg = sum(item.score for item in early) / max(len(early), 1)
    recent_avg = sum(item.score for item in recent) / max(len(recent), 1)
    delta = round((recent_avg - early_avg) / max(early_avg, 1) * 100, 1)
    return {
        "early_count": len(early),
        "recent_count": len(recent),
        "early_avg_score": round(early_avg, 1),
        "recent_avg_score": round(recent_avg, 1),
        "score_delta_pct": delta,
        "summary": "近期互动走强" if delta > 20 else ("近期互动走弱" if delta < -20 else "近期互动基本平稳"),
    }


def frequent_hashtags(posts: list[BloggerPost]) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for post in posts:
        try:
            tags = json.loads(post.hashtags_json or "[]")
        except json.JSONDecodeError:
            tags = []
        counts.update(str(tag) for tag in tags if str(tag).strip())
    return [{"tag": tag, "count": count} for tag, count in counts.most_common(20)]


def collect_comments(posts: list[BloggerPost]) -> list[dict[str, Any]]:
    comments: list[dict[str, Any]] = []
    for post in posts:
        try:
            comments.extend(json.loads(post.comments_json or "[]"))
        except json.JSONDecodeError:
            continue
    return comments


def extract_opinion_sentences(posts: list[BloggerPost]) -> list[str]:
    candidates: list[str] = []
    keywords = r"我觉得|我发现|其实|真正|关键|不要|一定|最好|建议|核心|本质"
    for post in posts:
        source_text = "\n".join(part for part in [post.body_text or "", post.transcript_text or "", post.image_text or ""] if part)
        sentences = re.split(r"[。！？!?]\s*", source_text)
        for sentence in sentences:
            clean = sentence.strip()
            if 12 <= len(clean) <= 120 and re.search(keywords, clean):
                candidates.append(clean)
    return candidates


def post_summary(post: BloggerPost) -> dict[str, Any]:
    comments = []
    try:
        comments = json.loads(post.comments_json or "[]")
    except json.JSONDecodeError:
        pass
    return {
        "id": post.id,
        "external_id": post.external_id,
        "title": post.title,
        "body_excerpt": post.body_text[:500],
        "content_type": post.content_type,
        "has_transcript": bool((post.transcript_text or "").strip()),
        "transcript_excerpt": (post.transcript_text or "")[:500],
        "asr_status": post.asr_status,
        "has_image_text": bool((post.image_text or "").strip()),
        "image_text_excerpt": (post.image_text or "")[:500],
        "visual_digest": visual_digest_dict(post),
        "hashtags": json.loads(post.hashtags_json or "[]"),
        "like_count": post.like_count,
        "favorite_count": post.favorite_count,
        "comment_count": post.comment_count,
        "sampled_comment_count": len(comments),
        "score": round(post.score, 2),
        "url": post.url,
        "top_comments": comments[:10],
    }
