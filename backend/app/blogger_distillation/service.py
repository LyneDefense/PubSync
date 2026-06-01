from __future__ import annotations

import html
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blogger_distillation.tikhub_client import (
    TikHubError,
    TikHubUsage,
    TikHubXhsClient,
    XhsPostCandidate,
    first_int,
    first_str,
    parse_timestamp,
    recursive_find,
    unwrap_payload,
)
from app.config import Settings
from app.models import BloggerDistillationRun, BloggerPost, BloggerProfile, BloggerSkill, OperationTaskEvent
from app.services.ai_service import AIServiceError, create_json_response


logger = logging.getLogger(__name__)


@dataclass
class DistillationResult:
    run: BloggerDistillationRun
    skill: BloggerSkill


def record_task_event(
    db: Session,
    tenant_id: int,
    task_id: str,
    step_name: str,
    status: str,
    message: str,
    payload: dict[str, Any] | None = None,
) -> None:
    logger.info("博主蒸馏事件：任务ID=%s，步骤=%s，状态=%s，%s", task_id, step_name, status, message)
    db.add(
        OperationTaskEvent(
            tenant_id=tenant_id,
            task_id=task_id,
            step_name=step_name,
            status=status,
            message=message,
            payload_json=json.dumps(payload, ensure_ascii=False, default=str) if payload else None,
        )
    )
    db.commit()


def create_blogger(db: Session, tenant_id: int, display_name: str, homepage_url: str, niche: str, description: str) -> BloggerProfile:
    existing = db.scalar(
        select(BloggerProfile).where(BloggerProfile.tenant_id == tenant_id, BloggerProfile.homepage_url == homepage_url)
    )
    if existing:
        existing.display_name = display_name
        existing.niche = niche
        existing.description = description
        db.commit()
        db.refresh(existing)
        return existing
    blogger = BloggerProfile(
        tenant_id=tenant_id,
        platform="xhs",
        display_name=display_name,
        homepage_url=homepage_url,
        niche=niche,
        description=description,
    )
    db.add(blogger)
    db.commit()
    db.refresh(blogger)
    return blogger


def run_blogger_distillation(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
) -> DistillationResult:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")

    run = BloggerDistillationRun(tenant_id=tenant_id, blogger_id=blogger.id, task_id=task_id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        record_task_event(db, tenant_id, task_id, "博主采集", "running", "开始通过 TikHub 采集小红书图文笔记")
        client = TikHubXhsClient(settings)
        user_info = client.get_user_info(blogger.homepage_url)
        candidates = client.get_user_notes(blogger.homepage_url, sample_limit)
        record_task_event(db, tenant_id, task_id, "博主采集", "running", f"已获取笔记候选 {len(candidates)} 条")

        posts = collect_posts(db, tenant_id, blogger, client, candidates[:sample_limit], comments_per_post)
        if not posts:
            raise TikHubError("没有采集到可用于蒸馏的图文笔记，请检查主页链接或 TikHub 接口返回")
        blogger.sample_count = len(posts)
        db.commit()
        record_task_event(db, tenant_id, task_id, "样本清洗", "succeeded", f"样本清洗完成：保留 {len(posts)} 条图文笔记")

        stats = analyze_posts(posts)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "基础统计",
            "succeeded",
            f"基础统计完成：爆款={len(stats['hot_posts'])}，评论={stats['comment_total']}",
        )

        record_task_event(db, tenant_id, task_id, "认知蒸馏", "running", "开始用大模型提炼认知、策略和执行层方法论")
        distillation = distill_with_llm(settings, blogger, user_info, stats)
        report_html = render_report_html(blogger, stats, distillation, client.usage)
        skill_markdown = build_skill_markdown(blogger, stats, distillation)
        skill = BloggerSkill(
            tenant_id=tenant_id,
            blogger_id=blogger.id,
            run_id=run.id,
            name=slug_skill_name(blogger.display_name),
            description=f"基于小红书博主 {blogger.display_name} 公开图文内容蒸馏出的创作方法论",
            skill_markdown=skill_markdown,
            status="active",
        )
        db.add(skill)

        run.status = "succeeded"
        run.sample_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        apply_usage(run, client.usage)
        run.report_json = json.dumps({"stats": stats, "distillation": distillation}, ensure_ascii=False, default=str)
        run.report_html = report_html
        blogger.last_distilled_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(run)
        db.refresh(skill)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "Skill 生成",
            "succeeded",
            f"蒸馏完成：TikHub 请求={client.usage.request_count}，估算费用=${client.usage.estimated_cost_usd:.4f}",
            {"run_id": run.id, "skill_id": skill.id},
        )
        return DistillationResult(run=run, skill=skill)
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        db.commit()
        raise


def collect_posts(
    db: Session,
    tenant_id: int,
    blogger: BloggerProfile,
    client: TikHubXhsClient,
    candidates: list[XhsPostCandidate],
    comments_per_post: int,
) -> list[BloggerPost]:
    posts: list[BloggerPost] = []
    for candidate in candidates:
        try:
            detail_payload = client.get_image_note_detail(candidate)
        except TikHubError as exc:
            logger.warning("图文详情采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            continue
        normalized = normalize_post(candidate, detail_payload)
        if not normalized["title"] and not normalized["body_text"]:
            continue
        comments = []
        try:
            comments = [normalize_comment(item) for item in client.get_note_comments(candidate, comments_per_post)]
        except TikHubError as exc:
            logger.warning("评论采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
        normalized["comments_json"] = json.dumps([item for item in comments if item["content"]], ensure_ascii=False)
        post = upsert_post(db, tenant_id, blogger, normalized)
        posts.append(post)
    db.commit()
    return posts


def normalize_post(candidate: XhsPostCandidate, detail_payload: dict[str, Any]) -> dict[str, Any]:
    payload = unwrap_payload(detail_payload)
    raw = payload if isinstance(payload, dict) else detail_payload
    interact = recursive_find(raw, "interact_info")
    if not isinstance(interact, dict):
        interact = raw
    hashtags = extract_hashtags(raw)
    media_urls = extract_media_urls(raw)
    title = first_str(raw, ["title", "display_title", "note_title"]) or first_str(candidate.raw, ["display_title", "title"])
    body = first_str(raw, ["desc", "description", "content", "note_desc", "text"])
    url = first_str(raw, ["share_url", "url", "web_url"]) or first_str(candidate.raw, ["share_url", "url"])
    published_at = parse_timestamp(
        recursive_find(raw, "time") or recursive_find(raw, "timestamp") or recursive_find(raw, "last_update_time")
    )
    like_count = first_int(interact, ["liked_count", "like_count", "likes"])
    favorite_count = first_int(interact, ["collected_count", "favorite_count", "collect_count"])
    comment_count = first_int(interact, ["comment_count", "comments"])
    share_count = first_int(interact, ["share_count", "shares"])
    score = like_count * 0.35 + favorite_count * 0.45 + comment_count * 0.2 + share_count * 0.05
    return {
        "external_id": candidate.external_id,
        "url": url,
        "title": title[:500] or "未命名笔记",
        "body_text": body,
        "hashtags_json": json.dumps(hashtags, ensure_ascii=False),
        "cover_url": media_urls[0] if media_urls else "",
        "media_urls_json": json.dumps(media_urls, ensure_ascii=False),
        "published_at": published_at,
        "like_count": like_count,
        "favorite_count": favorite_count,
        "comment_count": comment_count,
        "share_count": share_count,
        "score": score,
        "raw_json": json.dumps(detail_payload, ensure_ascii=False, default=str),
    }


def normalize_comment(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "content": first_str(item, ["content", "text", "comment_content", "desc"]),
        "like_count": first_int(item, ["like_count", "liked_count", "likes"]),
        "created_at": str(parse_timestamp(item.get("create_time") or item.get("time")) or ""),
    }


def upsert_post(db: Session, tenant_id: int, blogger: BloggerProfile, data: dict[str, Any]) -> BloggerPost:
    post = db.scalar(
        select(BloggerPost).where(
            BloggerPost.tenant_id == tenant_id,
            BloggerPost.blogger_id == blogger.id,
            BloggerPost.external_id == data["external_id"],
        )
    )
    if not post:
        post = BloggerPost(tenant_id=tenant_id, blogger_id=blogger.id, platform="xhs", **data)
        db.add(post)
        db.flush()
        return post
    for key, value in data.items():
        setattr(post, key, value)
    db.flush()
    return post


def extract_hashtags(raw: dict[str, Any]) -> list[str]:
    tags: set[str] = set()
    for key in ("tag_list", "hash_tag", "hashtags", "tags"):
        value = recursive_find(raw, key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    tags.add(item.lstrip("#"))
                elif isinstance(item, dict):
                    tag = first_str(item, ["name", "tag_name", "title"])
                    if tag:
                        tags.add(tag.lstrip("#"))
    text = " ".join([first_str(raw, ["title", "desc", "content"]), json.dumps(raw, ensure_ascii=False)[:2000]])
    for tag in re.findall(r"#([\w\u4e00-\u9fff-]+)", text):
        tags.add(tag)
    return sorted(tags)[:20]


def extract_media_urls(raw: dict[str, Any]) -> list[str]:
    urls: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"url", "trace_id", "file_id"} and isinstance(child, str) and child.startswith("http"):
                    urls.append(child)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    for key in ("image_list", "images_list", "images", "cover", "image"):
        value = recursive_find(raw, key)
        if value:
            visit(value)
    seen: set[str] = set()
    deduped = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            deduped.append(url)
    return deduped[:12]


def analyze_posts(posts: list[BloggerPost]) -> dict[str, Any]:
    sorted_posts = sorted(posts, key=lambda item: item.score, reverse=True)
    hot_count = min(10, max(3, int(len(sorted_posts) * 0.2))) if sorted_posts else 0
    hot_posts = sorted_posts[:hot_count]
    comments = []
    for post in posts:
        try:
            comments.extend(json.loads(post.comments_json or "[]"))
        except json.JSONDecodeError:
            continue
    return {
        "sample_count": len(posts),
        "comment_total": len(comments),
        "average_like": round(sum(item.like_count for item in posts) / max(len(posts), 1), 2),
        "average_favorite": round(sum(item.favorite_count for item in posts) / max(len(posts), 1), 2),
        "average_comment": round(sum(item.comment_count for item in posts) / max(len(posts), 1), 2),
        "favorite_like_ratio": round(sum(item.favorite_count for item in posts) / max(sum(item.like_count for item in posts), 1), 4),
        "title_patterns": detect_title_patterns(posts),
        "frequent_hashtags": frequent_hashtags(posts),
        "hot_posts": [post_summary(item) for item in hot_posts],
        "representative_posts": [post_summary(item) for item in sorted_posts[: min(20, len(sorted_posts))]],
        "comment_insights_source": comments[:100],
    }


def detect_title_patterns(posts: list[BloggerPost]) -> dict[str, int]:
    patterns = {
        "避坑型": r"别|不要|千万|踩坑|避坑|不建议",
        "数字清单型": r"\d+|一|二|三|四|五|六|七|八|九|十|几个|种|条",
        "问题型": r"为什么|怎么办|是不是|如何|怎么",
        "反常识型": r"其实|不是|反而|错了|真相",
        "人群定位型": r"新手|第一次|养猫人|养狗人|铲屎官|宝妈|打工人",
    }
    result = {key: 0 for key in patterns}
    for post in posts:
        for name, pattern in patterns.items():
            if re.search(pattern, post.title):
                result[name] += 1
    return result


def frequent_hashtags(posts: list[BloggerPost]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for post in posts:
        try:
            tags = json.loads(post.hashtags_json or "[]")
        except json.JSONDecodeError:
            tags = []
        for tag in tags:
            counts[str(tag)] = counts.get(str(tag), 0) + 1
    return [{"tag": tag, "count": count} for tag, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:20]]


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
        "hashtags": json.loads(post.hashtags_json or "[]"),
        "like_count": post.like_count,
        "favorite_count": post.favorite_count,
        "comment_count": post.comment_count,
        "score": round(post.score, 2),
        "url": post.url,
        "top_comments": comments[:10],
    }


def distill_with_llm(settings: Settings, blogger: BloggerProfile, user_info: dict[str, Any], stats: dict[str, Any]) -> dict[str, Any]:
    prompt = f"""
你是“博主蒸馏 skill”的分析器。请参考 blogger-distiller 的方法：脚本负责事实统计，你负责把公开图文内容提炼成可迁移的创作方法论。

边界：
- 不能冒充原博主。
- 不能复制原文、标题、图片或个人经历。
- 只能提炼公开内容中的选题、结构、表达策略、评论需求和创作边界。
- 输出必须是合法 JSON。

博主：
{json.dumps({"display_name": blogger.display_name, "homepage_url": blogger.homepage_url, "niche": blogger.niche, "description": blogger.description}, ensure_ascii=False)}

TikHub 用户信息摘要：
{json.dumps(user_info, ensure_ascii=False, default=str)[:4000]}

代码统计与代表样本：
{json.dumps(stats, ensure_ascii=False, default=str)[:18000]}

输出 JSON：
{{
  "positioning": "这个博主公开内容呈现出的账号定位",
  "audience": "目标读者画像",
  "cognitive_model": ["认知层方法论"],
  "topic_strategy": ["选题策略"],
  "title_patterns": ["标题规律"],
  "opening_patterns": ["开头规律"],
  "body_structures": ["正文结构"],
  "cover_text_rules": ["封面文案规律"],
  "hashtag_strategy": ["标签策略"],
  "comment_strategy": ["评论区洞察和互动策略"],
  "sample_topics": ["可迁移的新选题示例"],
  "do_not_do": ["禁止事项和不应模仿的部分"]
}}
"""
    data = create_json_response(settings, prompt)
    required = ["positioning", "audience", "cognitive_model", "topic_strategy", "title_patterns", "body_structures", "do_not_do"]
    for key in required:
        if key not in data:
            raise AIServiceError(f"博主蒸馏结果缺少字段：{key}")
    return data


def render_report_html(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any], usage: TikHubUsage) -> str:
    sections = [
        ("账号定位", distillation.get("positioning")),
        ("目标读者", distillation.get("audience")),
        ("认知模型", distillation.get("cognitive_model")),
        ("选题策略", distillation.get("topic_strategy")),
        ("标题规律", distillation.get("title_patterns")),
        ("正文结构", distillation.get("body_structures")),
        ("评论洞察", distillation.get("comment_strategy")),
        ("禁止事项", distillation.get("do_not_do")),
    ]
    hot_items = "".join(
        f"<li><strong>{html.escape(item['title'])}</strong><span> 收藏 {item['favorite_count']} / 点赞 {item['like_count']} / 评论 {item['comment_count']}</span></li>"
        for item in stats.get("hot_posts", [])
    )
    body = [
        f"<h1>{html.escape(blogger.display_name)} 小红书图文蒸馏报告</h1>",
        f"<p>样本 {stats['sample_count']} 条，评论 {stats['comment_total']} 条，TikHub 请求 {usage.request_count} 次，估算费用 ${usage.estimated_cost_usd:.4f}（区间 ${usage.cost_min_usd:.4f} - ${usage.cost_max_usd:.4f}）。</p>",
        "<h2>爆款样本</h2>",
        f"<ol>{hot_items}</ol>",
    ]
    for title, value in sections:
        body.append(f"<h2>{html.escape(title)}</h2>")
        if isinstance(value, list):
            body.append("<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in value) + "</ul>")
        else:
            body.append(f"<p>{html.escape(str(value or ''))}</p>")
    return "\n".join(body)


def build_skill_markdown(blogger: BloggerProfile, stats: dict[str, Any], distillation: dict[str, Any]) -> str:
    name = slug_skill_name(blogger.display_name)
    return f"""---
name: {name}
description: 基于小红书博主 {blogger.display_name} 公开图文内容蒸馏出的创作方法论。不要冒充原博主，不要复制原文。
---

# {blogger.display_name} 图文创作方法论 Skill

## 角色定位

你不是原博主本人，不要冒充原博主。你是学习了该博主公开图文内容方法论的创作助手，只迁移选题、结构、表达策略和读者洞察。

## 适用范围

- 平台：小红书图文笔记，也可迁移到公众号短内容选题。
- 领域：{blogger.niche or "与样本内容相近的垂直领域"}。
- 样本规模：{stats["sample_count"]} 条图文笔记，{stats["comment_total"]} 条评论。

## 账号定位

{distillation.get("positioning", "")}

## 目标读者

{distillation.get("audience", "")}

## 认知模型

{markdown_list(distillation.get("cognitive_model"))}

## 选题策略

{markdown_list(distillation.get("topic_strategy"))}

## 标题规则

{markdown_list(distillation.get("title_patterns"))}

## 开头规则

{markdown_list(distillation.get("opening_patterns"))}

## 正文结构

{markdown_list(distillation.get("body_structures"))}

## 封面文案

{markdown_list(distillation.get("cover_text_rules"))}

## 话题标签

{markdown_list(distillation.get("hashtag_strategy"))}

## 评论区策略

{markdown_list(distillation.get("comment_strategy"))}

## 当用户不知道发什么时

1. 先询问账号定位、目标用户、发布目标和禁区。
2. 生成 20 个候选选题。
3. 按收藏潜力、评论潜力、账号匹配度评分。
4. 推荐前 5 个，并说明为什么适合。

## 当用户已有主题时

1. 判断主题是否适合该方法论。
2. 输出 3 个标题方案。
3. 输出正文、封面文案、话题标签、配图建议和评论引导。

## 可迁移选题示例

{markdown_list(distillation.get("sample_topics"))}

## 禁止事项

{markdown_list(distillation.get("do_not_do"))}
- 不复制原博主原文。
- 不复用原博主图片。
- 不冒充原博主身份。
- 不虚构个人经历、病例、数据或用户反馈。
"""


def markdown_list(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(f"- {item}" for item in value) or "- 暂无"
    if value:
        return f"- {value}"
    return "- 暂无"


def slug_skill_name(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff_-]+", "-", name.strip()).strip("-").lower()
    return f"xhs-{slug or 'blogger'}-distilled"


def apply_usage(run: BloggerDistillationRun, usage: TikHubUsage) -> None:
    run.tikhub_request_count = usage.request_count
    run.tikhub_estimated_cost_usd = round(usage.estimated_cost_usd, 6)
    run.tikhub_cost_min_usd = round(usage.cost_min_usd, 6)
    run.tikhub_cost_max_usd = round(usage.cost_max_usd, 6)
