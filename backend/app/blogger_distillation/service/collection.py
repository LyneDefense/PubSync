from __future__ import annotations

import json
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

import httpx

from sqlalchemy.orm import Session

from app.blogger_distillation import analysis
from app.blogger_distillation.modality import CONF_AMBIGUOUS, CONF_LLM, candidate_modality
from app.blogger_distillation.modality_adjudicator import adjudicate_modality
from app.blogger_distillation.providers import ensure_collection_provider_available
from app.blogger_distillation.quality import quality_report
from app.blogger_distillation.service.note_pipeline import build_collect_providers, process_one_note
from app.blogger_distillation.service.vision_step import revise_post_vision
from app.blogger_distillation.service.selection import select_detail_targets
from app.blogger_distillation.service.events import (
    DistillationCancelled,
    ensure_distillation_not_cancelled,
    record_task_event,
)
from app.blogger_distillation.service.usage import apply_usage
from app.blogger_dossier import pool as note_pool
from app.blogger_distillation.tikhub_client import (
    TikHubDouyinClient,
    TikHubError,
    TikHubXhsClient,
    XhsPostCandidate,
    build_platform_client,
)
from app.blogger_distillation.tikhub_client.parsers import parse_xhs_note_link
from app.blogger_distillation.search import extract_user_profile
from app.config import Settings
from app.database import SessionLocal
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
    return build_platform_client(settings, platform)


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
    backfill: bool = True,
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
            _apply_user_facts(blogger, extract_user_profile(blogger.platform, user_info))
        except Exception as exc:  # noqa: BLE001 — 解析博主资料失败不影响采集
            logger.warning("解析博主资料失败:blogger_id=%s,error=%s", blogger.id, exc)
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        # 先把笔记池(库内该博主已有 external_id)读出来,翻页时据此判断"新/旧"。
        existing = {
            post.external_id: post
            for post in db.scalars(
                select(BloggerPost).where(BloggerPost.tenant_id == tenant_id, BloggerPost.blogger_id == blogger.id)
            )
        }
        selected_modalities = {m for m in (content_types or ["image", "video"]) if m in ("image", "video")} or {"image", "video"}

        # "需要详情" = 池里没有,或只有列表级行(list 级行本就是"未抓详情",视同新增去升级)。
        def _needs_detail(c: XhsPostCandidate) -> bool:
            post = existing.get(c.external_id)
            return post is None or post.detail_level != "full"

        # 动态翻页:最新优先翻到"需要详情的够 N 条"就停;高赞优先/全部翻到底(或安全上限)再排序。
        def _new_in_range(cands: list[XhsPostCandidate]) -> int:
            return sum(1 for c in cands if _needs_detail(c) and candidate_modality(c.note_type) in selected_modalities)

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

        # 增量:从"需要详情的"里按排序取最多 N 条当新增(含 list 级行升级);已是详情级的顺带刷新。
        new_candidates = [c for c in candidates if _needs_detail(c)]
        existing_candidates = [(c, existing[c.external_id]) for c in candidates if not _needs_detail(c)]
        if order == "smart":  # 建档/升详情:高赞+最近优先 + 动态 K 爆文保底(用全量候选算中位数/总数)
            new_targets = select_detail_targets(
                new_candidates, total=len(candidates), limit=sample_limit,
                hot_ratio=settings.dossier_hot_ratio, hot_floor=settings.dossier_hot_floor, hot_cap=settings.dossier_hot_cap,
            )
        else:
            new_targets = select_targets(new_candidates, order, fetch_all, sample_limit)

        to_fetch: list[XhsPostCandidate] = list(new_targets)  # 新笔记
        new_count = len(new_targets)
        backfill_count = 0
        vision_enabled = settings.vision_enabled
        refresh_only: list[tuple[XhsPostCandidate, BloggerPost]] = []
        for candidate, post in existing_candidates:
            # 补转写:视频 URL 易过期,需重抓该条详情;补图片理解:封面/图 URL 同样会过期。
            # backfill=False(用户在大回填确认框选了"否")时,存量一律只走轻量刷新,不回填。
            need_asr = backfill and candidate.note_type == "video" and asr_enabled and post.asr_status in ("skipped", "failed")
            need_vision = backfill and vision_enabled and post.vision_status != "succeeded"
            if need_asr or need_vision:
                to_fetch.append(candidate)
                backfill_count += 1
            else:
                refresh_only.append((candidate, post))
        record_task_event(
            db, tenant_id, task_id, "增量分流", "succeeded",
            f"候选 {len(candidates)} 条：本次新增 {new_count} · 补采(转写/图片) {backfill_count} · 刷新已有 {len(refresh_only)}"
            + (f"（候选里没采过的只剩 {len(new_candidates)} 条，不足目标 {sample_limit}）" if not fetch_all and len(new_candidates) < sample_limit else ""),
            {"new": new_count, "backfill": backfill_count, "refresh": len(refresh_only), "total": len(to_fetch)},
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
            post.status = "active" if post.status != "excluded" else "excluded"
        # 老笔记轻量刷新:用列表卡数据更新(互动/浏览/时间/token) + last_seen,不抓详情。
        for candidate, post in refresh_only:
            note_pool.refresh_from_candidate(post, candidate)
            post.status = "active" if post.status != "excluded" else "excluded"

        # 笔记池全量落库:没被选中升级详情的候选也 upsert 为 list 级行(此前直接丢弃),统计/轨迹靠它。
        fetch_ids = {c.external_id for c in to_fetch}
        leftovers = [c for c in all_candidates if c.external_id not in existing and c.external_id not in fetch_ids]
        if leftovers:
            pool_counts = note_pool.upsert_list_candidates(db, tenant_id, blogger, leftovers)
            record_task_event(
                db, tenant_id, task_id, "笔记池", "succeeded",
                f"列表候选全量入池:新增列表级 {pool_counts['new']} 条(仅标题/时间/互动,未抓详情)",
            )
        blogger.pool_synced_at = now
        if notes_result.reached_end:
            blogger.pool_reached_end = True

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


def _apply_user_facts(blogger: BloggerProfile, profile: dict[str, object]) -> None:
    """把 user_info 解析出的「平台事实」写入 profile(采集/刷新共用):笔记总数 / 主页简介 / 账号级获赞收藏。
    display_name/avatar/follower 只在「刷新博主」覆盖,采集不动(避免采集顺带改名)。"""
    if profile.get("note_total") is not None:
        blogger.note_total = profile["note_total"]
    if profile.get("signature"):
        blogger.signature = profile["signature"]
    if profile.get("liked_collected_count") is not None:
        blogger.liked_collected_count = profile["liked_collected_count"]


def refresh_blogger_profile(db: Session, settings: Settings, tenant_id: int, blogger_id: int) -> BloggerProfile:
    """重新拉取博主资料(昵称/头像/粉丝数/笔记总数/主页简介/获赞收藏)并覆盖。供「刷新博主」按钮用,一次 user_info 调用。"""
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
    _apply_user_facts(blogger, profile)
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
            post.status = "active" if post.status != "excluded" else "excluded"
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
    providers = build_collect_providers(db, tenant_id, task_id, settings)
    total = len(candidates)
    concurrency = max(1, settings.collect_concurrency)
    cancel_event = threading.Event()
    progress = {"done": 0}
    progress_lock = threading.Lock()

    def _collect_one(item: tuple[int, XhsPostCandidate]) -> int | None:
        """并发处理一篇:独立 DB session,进度用完成计数。返回入库 post.id 或 None。"""
        _, candidate = item
        if cancel_event.is_set():
            return None
        session = SessionLocal()
        try:
            with progress_lock:
                progress["done"] += 1
                current = progress["done"]
            post = process_one_note(
                session, tenant_id, task_id, blogger, client, settings, candidate, comments_per_post, providers,
                current=current, total=total,
            )
            session.commit()
            return post.id if post is not None else None
        except DistillationCancelled:
            cancel_event.set()  # 取消:标记后让剩余任务快速跳过
            session.rollback()
            return None
        except Exception:  # noqa: BLE001 — 单篇异常隔离,不掀翻整批(管线内已记事件)
            session.rollback()
            logger.exception("采集单篇失败:note_id=%s", candidate.external_id)
            return None
        finally:
            session.close()

    # 每篇独立 session 并发处理:IO 密集(TikHub/CDN/GLM 等待),GIL 不挡网络;并发度即 GLM 视觉并发闸。
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        post_ids = list(executor.map(_collect_one, enumerate(candidates, 1)))
    if cancel_event.is_set():
        raise DistillationCancelled("用户已请求停止流程，流程安全退出；已采集样本会保留")

    # 子线程 session 已关闭、post 对象 detached;用主 session 按 id 重取,供模态裁决/后续 run 逻辑使用。
    ids = [pid for pid in post_ids if pid is not None]
    posts = list(db.scalars(select(BloggerPost).where(BloggerPost.id.in_(ids)))) if ids else []
    _retry_failed_vision(db, tenant_id, task_id, posts, providers.vision, settings)
    _adjudicate_ambiguous_modality(db, tenant_id, task_id, posts, settings)
    return posts


def _retry_failed_vision(db: Session, tenant_id: int, task_id: str, posts: list[BloggerPost], vision_provider, settings: Settings) -> None:
    """收尾补采:主流程跑完后,对图片理解 failed 的笔记当场再试一轮(并发峰值已过、又走重试+限并发,成功率高)。"""
    if vision_provider is None:
        return
    failed = [p for p in posts if p.vision_status == "failed"]
    if not failed:
        return
    record_task_event(db, tenant_id, task_id, "图片理解", "running", f"收尾补采 {len(failed)} 条图片理解失败的笔记…")
    fixed = 0
    for post in failed:
        ensure_distillation_not_cancelled(db, tenant_id, task_id)
        if revise_post_vision(post, vision_provider, settings):
            fixed += 1
    db.commit()
    record_task_event(db, tenant_id, task_id, "图片理解", "succeeded", f"收尾补采完成:{fixed}/{len(failed)} 条补齐")


def _adjudicate_ambiguous_modality(
    db: Session, tenant_id: int, task_id: str, posts: list[BloggerPost], settings: Settings
) -> None:
    """T2 语义裁决:密度判不清的模糊视频(半口播/剧情/卡点),批量交大模型判口播/非口播;
    仅少数、成本有界,失败则保留 T1 密度猜测,绝不阻断采集。"""
    if not settings.modality_llm_adjudicate_enabled:
        return
    ambiguous = [p for p in posts if p.content_subtype_confidence == CONF_AMBIGUOUS]
    if not ambiguous:
        return
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
