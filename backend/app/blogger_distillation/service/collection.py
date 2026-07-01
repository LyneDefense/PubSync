from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

import httpx

from sqlalchemy.orm import Session

from app.blogger_distillation import analysis
from app.blogger_distillation.asr import ASRError, build_asr_provider
from app.blogger_distillation.modality import CONF_AMBIGUOUS, CONF_LLM, candidate_modality, classify_subtype
from app.blogger_distillation.modality_adjudicator import adjudicate_modality
from app.blogger_distillation.privacy import anonymize_comments
from app.blogger_distillation.providers import ensure_collection_provider_available
from app.blogger_distillation.quality import evaluate_post_quality, quality_report
from app.blogger_distillation.service.asr_step import handle_video_asr
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
)
from app.blogger_distillation.service.extract import (
    extract_video_url,
    normalize_comment,
    normalize_post,
    supplement_video_detail_with_url,
    upsert_post,
)
from app.blogger_distillation.service.usage import apply_usage
from app.blogger_distillation.tikhub_client import (
    TikHubDouyinClient,
    TikHubError,
    TikHubXhsClient,
    XhsPostCandidate,
)
from app.blogger_distillation.tikhub_client.parsers import detect_note_type, parse_xhs_note_link
from app.blogger_distillation.search import extract_user_profile
from app.config import Settings
from app.models import BloggerCollectionPost, BloggerCollectionRun, BloggerPost, BloggerProfile
from app.models.common import utc_now
from sqlalchemy import func, select

logger = logging.getLogger(__name__)


def select_targets(
    candidates: list[XhsPostCandidate], order: str, fetch_all: bool, sample_limit: int
) -> list[XhsPostCandidate]:
    """按排序策略选出目标集。top_liked=列表赞数降序;latest=保持主页顺序(≈最新在前)。"""
    pool = list(candidates)
    if order == "top_liked":
        pool.sort(key=lambda c: c.like_count or 0, reverse=True)
    return pool if fetch_all else pool[:sample_limit]


@dataclass
class CollectionResult:
    run: BloggerCollectionRun


def build_collection_client(settings: Settings, platform: str) -> TikHubXhsClient | TikHubDouyinClient:
    if platform == "douyin":
        return TikHubDouyinClient(settings)
    return TikHubXhsClient(settings)


def platform_collection_label(platform: str) -> str:
    return "抖音作品" if platform == "douyin" else "小红书笔记"


def _apply_auto_tags(
    db: Session,
    settings: Settings,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    posts: list[BloggerPost],
    stats: dict,
) -> None:
    """采集完成后用 LLM 给博主打内容标签。失败只记事件、绝不让采集失败。"""
    if not settings.blogger_auto_tag_enabled:
        return
    try:
        from app.blogger_distillation.service.tagging import generate_auto_tags, merge_tags

        record_task_event(db, tenant_id, task_id, "内容标签", "running", "正在提炼内容标签")
        model = (settings.blogger_tag_model or settings.distill_text_model or "").strip() or None
        limit = max(1, settings.blogger_tag_max)
        new_auto = generate_auto_tags(settings, blogger, posts, stats, model=model, limit=limit)
        blogger.tags_json = merge_tags(blogger.tags_json, new_auto, limit=limit)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "内容标签",
            "succeeded",
            f"已生成内容标签:{('、'.join(new_auto)) or '(无)'}",
            {"tags": new_auto},
        )
    except Exception as exc:  # noqa: BLE001 — 打标签是增强项,不能影响采集主流程
        logger.warning("自动打标签失败,跳过:blogger_id=%s,error=%s", blogger.id, exc)
        try:
            record_task_event(db, tenant_id, task_id, "内容标签", "running", f"内容标签生成失败,已跳过:{exc}")
        except Exception:  # noqa: BLE001
            pass


def run_blogger_collection(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
    asr_enabled: bool = False,
    content_types: list[str] | None = None,
    order: str = "top_liked",
    fetch_all: bool = False,
) -> CollectionResult:
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")

    run = BloggerCollectionRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        task_id=task_id,
        status="running",
        sample_limit=sample_limit,
        comments_per_post=comments_per_post,
        asr_enabled=asr_enabled,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    collection_settings = settings.model_copy(update={"asr_enabled": asr_enabled})

    client: TikHubXhsClient | TikHubDouyinClient | None = None
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "样本采集", "running", "开始采集数据")
        ensure_collection_provider_available(blogger)
        client = build_collection_client(collection_settings, blogger.platform)
        user_info = client.get_user_info(blogger.homepage_url, blogger.external_id)
        try:
            parsed_total = extract_user_profile(blogger.platform, user_info).get("note_total")
            if parsed_total is not None:
                blogger.note_total = parsed_total
        except Exception as exc:  # noqa: BLE001 — 解析笔记总数失败不影响采集
            logger.warning("解析博主笔记总数失败:blogger_id=%s,error=%s", blogger.id, exc)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        # 先把笔记池(库内该博主已有 external_id)读出来,翻页时据此判断"新/旧"。
        existing = {
            post.external_id: post
            for post in db.scalars(
                select(BloggerPost).where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id)
            )
        }
        selected_modalities = {m for m in (content_types or ["image", "video"]) if m in ("image", "video")} or {"image", "video"}

        # 动态翻页:最新优先翻到"没采过的够 N 条"就停;高赞优先/全部翻到底(或安全上限)再排序。
        def _new_in_range(cands: list[XhsPostCandidate]) -> int:
            return sum(
                1 for c in cands
                if c.external_id not in existing and candidate_modality(c.note_type) in selected_modalities
            )

        def _should_stop(cands: list[XhsPostCandidate]) -> bool:
            if fetch_all or order != "latest":
                return False  # 高赞/全部:必须看全才能排序,不早停
            return _new_in_range(cands) >= sample_limit  # 最新:够 N 条没采过的就停

        notes_result = client.get_user_notes(
            blogger.homepage_url, settings.candidate_pool_cap, blogger.external_id, should_stop=_should_stop
        )
        all_candidates = notes_result.candidates
        record_task_event(
            db, tenant_id, task_id, "样本采集", "running",
            f"已获取笔记候选 {len(all_candidates)} 条" + ("（已翻到列表底部）" if notes_result.reached_end else ""),
        )

        # 拉取范围过滤(图文/视频)。
        candidates = [c for c in all_candidates if candidate_modality(c.note_type) in selected_modalities]
        if not candidates:
            raise TikHubError(f"没有符合条件的{platform_collection_label(blogger.platform)}候选，请检查主页链接、拉取范围或 TikHub 返回")

        # 增量:从"没采过的"里按排序取最多 N 条当新增;已采过的(在候选里)顺带刷新。
        new_candidates = [c for c in candidates if c.external_id not in existing]
        existing_candidates = [(c, existing[c.external_id]) for c in candidates if c.external_id in existing]
        new_targets = select_targets(new_candidates, order, fetch_all, sample_limit)

        to_fetch: list[XhsPostCandidate] = list(new_targets)  # 新笔记
        new_count = len(new_targets)
        backfill_count = 0
        refresh_only: list[tuple[XhsPostCandidate, BloggerPost]] = []
        for candidate, post in existing_candidates:
            if candidate.note_type == "video" and asr_enabled and post.asr_status in ("skipped", "failed"):
                to_fetch.append(candidate)  # 补转写:视频 URL 易过期,需重抓该条详情
                backfill_count += 1
            else:
                refresh_only.append((candidate, post))
        record_task_event(
            db, tenant_id, task_id, "增量分流", "succeeded",
            f"候选 {len(candidates)} 条：本次新增 {new_count} · 补转写 {backfill_count} · 刷新已有 {len(refresh_only)}"
            + (f"（候选里没采过的只剩 {len(new_candidates)} 条，不足目标 {sample_limit}）" if not fetch_all and len(new_candidates) < sample_limit else ""),
        )

        # 抓详情(仅新笔记 + 补 ASR);老笔记不重抓,只用列表数据刷新。
        fetched: list[BloggerPost] = []
        if to_fetch:
            fetched = collect_posts(db, tenant_id, task_id, blogger, client, collection_settings, to_fetch, comments_per_post)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)

        now = utc_now()
        # content_subtype 已在 collect_posts 入库前定好,这里只更新生命周期字段。
        for post in fetched:
            post.last_seen_at = now
            post.status = "active"
        # 老笔记轻量刷新:用列表赞藏数更新 + last_seen,不抓详情。
        for candidate, post in refresh_only:
            if candidate.like_count:
                post.like_count = candidate.like_count
            if candidate.favorite_count:
                post.favorite_count = candidate.favorite_count
            if candidate.comment_count:
                post.comment_count = candidate.comment_count
            if candidate.share_count:
                post.share_count = candidate.share_count
            post.last_seen_at = now
            post.status = "active"

        # 下架对账:仅当翻到列表底部(看到完整目录)才动。小红书翻页返回不稳定(同一博主两次"翻到底"
        # 拿到的集合可能不同),故需「连续 N 次完整爬取都缺失」才下架,单次缺失只累计、不下架,避免误杀。
        delisted_count = 0
        if notes_result.reached_end and settings.blogger_auto_delist_enabled:
            seen_ids = {c.external_id for c in all_candidates}
            threshold = max(1, settings.delist_after_consecutive_misses)
            for ext_id, post in existing.items():
                if post.status != "active":
                    continue
                if ext_id in seen_ids:
                    post.missed_crawl_count = 0
                else:
                    post.missed_crawl_count = (post.missed_crawl_count or 0) + 1
                    if post.missed_crawl_count >= threshold:
                        post.status = "delisted"
                        delisted_count += 1
            if delisted_count:
                record_task_event(db, tenant_id, task_id, "下架对账", "succeeded", f"对账完成：{delisted_count} 篇连续 {threshold} 次未出现，标记下架")

        # 本批成员 = 本次覆盖到的 post(新增 + 刷新/补转写的已有),先新后旧。
        fetched_map = {post.external_id: post for post in fetched}
        member_candidates = list(new_targets) + [candidate for candidate, _ in existing_candidates]
        member_posts: list[BloggerPost] = []
        seen_member_ids: set[int] = set()
        for candidate in member_candidates:
            post = fetched_map.get(candidate.external_id) or existing.get(candidate.external_id)
            if post is not None and post.id not in seen_member_ids:
                member_posts.append(post)
                seen_member_ids.add(post.id)
        if not member_posts:
            raise TikHubError(f"没有采集到可用的{platform_collection_label(blogger.platform)}样本，请检查主页链接或 TikHub 接口返回")

        posts = member_posts
        # 笔记池总量(该博主在架笔记数),作为博主层面的"已采集"展示。
        blogger.sample_count = int(
            db.scalar(
                select(func.count(BloggerPost.id)).where(
                    BloggerPost.tenant_id == tenant_id,
                    BloggerPost.blogger_id == blogger.id,
                    BloggerPost.status != "delisted",
                )
            )
            or len(posts)
        )
        for position, post in enumerate(posts, 1):
            db.add(
                BloggerCollectionPost(
                    tenant_id=tenant_id,
                    blogger_id=blogger.id,
                    collection_run_id=run.id,
                    post_id=post.id,
                    position=position,
                )
            )
        record_task_event(
            db, tenant_id, task_id, "样本清洗", "succeeded",
            f"样本清洗完成：本批 {len(posts)} 条（新增 {new_count}、刷新 {len(refresh_only) + backfill_count}）",
        )

        quality = quality_report(posts, sample_limit)
        if quality["warnings"]:
            record_task_event(db, tenant_id, task_id, "样本质量", "running", "；".join(quality["warnings"]), quality)
        else:
            record_task_event(db, tenant_id, task_id, "样本质量", "succeeded", "样本质量校验通过", quality)

        stats = analysis.analyze_posts(posts)
        stats["quality_report"] = quality
        _apply_auto_tags(db, settings, tenant_id, task_id, blogger, posts, stats)
        run.status = "succeeded"
        run.post_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.summary_json = json.dumps(
            {
                "stats": stats,
                "quality_report": quality,
                "collect_meta": {
                    "order": order,
                    "fetch_all": fetch_all,
                    "content_types": sorted(selected_modalities),
                    "new_count": new_count,
                    "refreshed_count": len(refresh_only) + backfill_count,
                    "delisted_count": delisted_count,
                    "reached_end": notes_result.reached_end,
                },
            },
            ensure_ascii=False,
            default=str,
        )
        apply_usage(run, client.usage)
        db.commit()
        db.refresh(run)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "基础统计",
            "succeeded",
            f"基础统计完成：爆款={len(stats['hot_posts'])}，评论={stats['comment_total']}，标题模式={len(stats['title_patterns'])}",
            {"collection_run_id": run.id},
        )
        return CollectionResult(run=run)
    except DistillationCancelled as exc:
        run.status = "cancelled"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise


def refresh_blogger_profile(db: Session, settings: Settings, tenant_id: int, blogger_id: int) -> BloggerProfile:
    """重新拉取博主资料(昵称/头像/粉丝数/笔记总数)并覆盖。供「刷新博主」按钮用,一次 user_info 调用。"""
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    ensure_collection_provider_available(blogger)
    client = build_collection_client(settings, blogger.platform)
    payload = client.get_user_info(blogger.homepage_url, blogger.external_id)
    profile = extract_user_profile(blogger.platform, payload)
    if profile["display_name"]:
        blogger.display_name = profile["display_name"]
    if profile["avatar_url"]:
        blogger.avatar_url = profile["avatar_url"]
    if profile["follower_count"]:
        blogger.follower_count = profile["follower_count"]
    if profile["note_total"] is not None:
        blogger.note_total = profile["note_total"]
    db.commit()
    db.refresh(blogger)
    return blogger


def _expand_short_link(text: str) -> str:
    """小红书短链(xhslink.com)跟一次重定向展开成带 token 的完整链接;其它原样返回。"""
    found = re.search(r"https?://\S+", text or "")
    url = found.group(0) if found else (text or "")
    if "xhslink.com" not in url:
        return text
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=10.0)
        return str(resp.url)
    except Exception as exc:  # noqa: BLE001
        logger.warning("短链展开失败:%s，错误=%s", url, exc)
        return text


def run_blogger_url_collection(
    db: Session,
    settings: Settings,
    task_id: str,
    tenant_id: int,
    blogger_id: int,
    urls: list[str],
    comments_per_post: int = 20,
    asr_enabled: bool = False,
) -> CollectionResult:
    """兜底:按粘贴的笔记链接定向采集,补进该博主笔记池(目前仅小红书)。"""
    blogger = db.get(BloggerProfile, blogger_id)
    if not blogger or blogger.tenant_id != tenant_id:
        raise ValueError("博主不存在或不属于当前工作空间")
    if blogger.platform != "xhs":
        raise ValueError("目前仅支持小红书笔记链接定向采集")

    collection_settings = settings.model_copy(update={"asr_enabled": asr_enabled})
    run = BloggerCollectionRun(
        tenant_id=tenant_id,
        blogger_id=blogger.id,
        task_id=task_id,
        status="running",
        sample_limit=len(urls),
        comments_per_post=comments_per_post,
        asr_enabled=asr_enabled,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    client: TikHubXhsClient | TikHubDouyinClient | None = None
    try:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(db, tenant_id, task_id, "定向采集", "running", f"开始按 {len(urls)} 条链接定向采集")
        ensure_collection_provider_available(blogger)
        client = build_collection_client(collection_settings, blogger.platform)

        candidates: list[XhsPostCandidate] = []
        seen: set[str] = set()
        for raw in urls:
            try:
                parsed = parse_xhs_note_link(_expand_short_link(raw))
            except TikHubError as exc:
                record_task_event(db, tenant_id, task_id, "链接解析", "failed", f"跳过无法解析的链接：{raw[:80]} — {exc}")
                continue
            if parsed["note_id"] in seen:
                continue
            seen.add(parsed["note_id"])
            candidates.append(
                XhsPostCandidate(
                    external_id=parsed["note_id"],
                    xsec_token=parsed["xsec_token"],
                    note_type="",
                    like_count=0,
                    favorite_count=0,
                    comment_count=0,
                    share_count=0,
                    raw={},
                )
            )
        if not candidates:
            raise TikHubError("没有可解析的笔记链接,请确认粘贴的是小红书笔记「分享链接」(需带 xsec_token)")

        posts = collect_posts(db, tenant_id, task_id, blogger, client, collection_settings, candidates, comments_per_post)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        if not posts:
            raise TikHubError("链接对应的笔记都未能采集成功(可能已删除、不可见或链接缺 token)")

        now = utc_now()
        # content_subtype 已在 collect_posts 入库前定好,这里只更新生命周期字段。
        for post in posts:
            post.last_seen_at = now
            post.status = "active"
        blogger.sample_count = len(posts)
        for position, post in enumerate(posts, 1):
            db.add(
                BloggerCollectionPost(
                    tenant_id=tenant_id,
                    blogger_id=blogger.id,
                    collection_run_id=run.id,
                    post_id=post.id,
                    position=position,
                )
            )

        quality = quality_report(posts, len(posts))
        stats = analysis.analyze_posts(posts)
        stats["quality_report"] = quality
        _apply_auto_tags(db, settings, tenant_id, task_id, blogger, posts, stats)
        run.status = "succeeded"
        run.post_count = len(posts)
        run.hot_post_count = len(stats["hot_posts"])
        run.comment_count = stats["comment_total"]
        run.summary_json = json.dumps(
            {"stats": stats, "quality_report": quality, "collect_meta": {"source": "url", "url_count": len(urls), "collected": len(posts)}},
            ensure_ascii=False,
            default=str,
        )
        apply_usage(run, client.usage)
        db.commit()
        db.refresh(run)
        record_task_event(
            db, tenant_id, task_id, "定向采集", "succeeded",
            f"定向采集完成：{len(urls)} 条链接 → 成功 {len(posts)} 条",
            {"collection_run_id": run.id},
        )
        return CollectionResult(run=run)
    except DistillationCancelled as exc:
        run.status = "cancelled"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise
    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)
        if client:
            apply_usage(run, client.usage)
        db.commit()
        raise


def collect_posts(
    db: Session,
    tenant_id: int,
    task_id: str,
    blogger: BloggerProfile,
    client: TikHubXhsClient | TikHubDouyinClient,
    settings: Settings,
    candidates: list[XhsPostCandidate],
    comments_per_post: int,
) -> list[BloggerPost]:
    posts: list[BloggerPost] = []
    asr_provider = None
    if settings.asr_enabled:
        try:
            asr_provider = build_asr_provider(settings)
            record_task_event(db, tenant_id, task_id, "视频 ASR", "running", f"ASR 已开启：provider={settings.asr_provider}")
        except ASRError as exc:
            record_task_event(db, tenant_id, task_id, "视频 ASR", "failed", f"ASR 初始化失败，将降级分析视频：{exc}")
            asr_provider = None
    else:
        record_task_event(db, tenant_id, task_id, "视频 ASR", "succeeded", "ASR 未开启，视频样本将使用标题、描述、评论和互动数据参与蒸馏")

    total = len(candidates)
    for index, candidate in enumerate(candidates, 1):
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "笔记详情",
            "running",
            "采集",
            {"current": index, "total": total, "type": candidate.note_type, "note_id": candidate.external_id},
        )
        try:
            detail_payload = client.get_image_note_detail(candidate)
        except TikHubError as exc:
            logger.warning("图文详情采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            record_task_event(db, tenant_id, task_id, "笔记详情", "failed", f"详情采集失败：note_id={candidate.external_id}，错误={exc}")
            continue
        # candidate.note_type 可能为空(URL 定向采集),此时从详情体里判定;视频则确保拿到直链。
        effective_type = candidate.note_type or detect_note_type(detail_payload)
        if effective_type == "video" and not extract_video_url(detail_payload):
            detail_payload = supplement_video_detail_with_url(client, candidate, detail_payload)
        normalized = normalize_post(candidate, detail_payload)
        if not normalized["title"] and not normalized["body_text"]:
            record_task_event(db, tenant_id, task_id, "样本清洗", "failed", f"跳过空内容笔记：note_id={candidate.external_id}")
            continue
        if normalized["content_type"] == "video":
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
            handle_video_asr(db, tenant_id, task_id, candidate, normalized, asr_provider, blogger)
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
        comments = []
        try:
            ensure_distillation_not_cancelled(db, tenant_id, task_id)
            raw_comments = anonymize_comments(client.get_note_comments(candidate, comments_per_post))
            comments = [normalize_comment(item) for item in raw_comments]
        except TikHubError as exc:
            logger.warning("评论采集失败：note_id=%s，错误=%s", candidate.external_id, exc)
            record_task_event(db, tenant_id, task_id, "评论采集", "failed", f"评论采集失败：note_id={candidate.external_id}，错误={exc}")
        normalized["comments_json"] = json.dumps([item for item in comments if item["content"]], ensure_ascii=False)
        # 在入库前定模态(T0平台+T1密度):转写/时长此刻已确定,保证每条存库的 content_subtype 与其转写一致。
        subtype, confidence = classify_subtype(
            normalized["content_type"],
            normalized.get("transcript_text", ""),
            duration_seconds=normalized.get("duration_seconds"),
            density_high_cps=settings.modality_density_high_cps,
            density_low_cps=settings.modality_density_low_cps,
            min_transcript_chars=settings.talking_video_min_transcript_chars,
        )
        normalized["content_subtype"] = subtype
        normalized["content_subtype_confidence"] = confidence
        post_quality = evaluate_post_quality(normalized)
        if post_quality.level == "failed":
            logger.warning("笔记质量不合格，跳过：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
            continue
        if post_quality.level == "partial":
            logger.info("笔记质量部分可用：note_id=%s，缺失=%s", candidate.external_id, ",".join(post_quality.missing))
        post = upsert_post(db, tenant_id, blogger, normalized)
        posts.append(post)
        record_task_event(
            db,
            tenant_id,
            task_id,
            "样本入库",
            "succeeded",
            "已保存样本",
            {"current": index, "total": total, "post_id": post.id, "note_id": candidate.external_id, "asr": normalized["asr_status"]},
        )
    db.commit()
    # T2 语义裁决:密度判不清的模糊视频(半口播/剧情/卡点),批量交大模型判口播/非口播;
    # 仅少数、成本有界,失败则保留 T1 密度猜测,绝不阻断采集。
    if settings.modality_llm_adjudicate_enabled:
        ambiguous = [p for p in posts if p.content_subtype_confidence == CONF_AMBIGUOUS]
        if ambiguous:
            record_task_event(db, tenant_id, task_id, "模态裁决", "running", f"{len(ambiguous)} 条视频密度判不清,语义裁决中…")
            verdicts = adjudicate_modality(
                [{"id": p.id, "title": p.title, "transcript": p.transcript_text, "duration": p.duration_seconds} for p in ambiguous],
                settings,
            )
            changed = 0
            for p in ambiguous:
                verdict = verdicts.get(p.id)
                if not verdict:
                    continue
                if verdict != p.content_subtype:
                    changed += 1
                p.content_subtype = verdict
                p.content_subtype_confidence = CONF_LLM
            db.commit()
            record_task_event(
                db, tenant_id, task_id, "模态裁决", "succeeded",
                f"语义裁决完成:{len(verdicts)}/{len(ambiguous)} 条判定,{changed} 条修正",
            )
    return posts
