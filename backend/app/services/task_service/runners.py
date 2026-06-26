"""各业务的后台任务入口(``run_*_task``):每个都用 :func:`execute_task` 包一层,
只在 ``work`` 回调里写自己的步骤(标 running → 调对应 service → 标 succeeded)。

``build_pipeline`` 装配公众号那条流水线(抓取/生成/发布),供新闻/文章/每日发布三个任务复用。
"""

import logging

from sqlalchemy.orm import Session

from app.blogger_distillation.service import (
    record_task_event,
    run_blogger_collection,
    run_blogger_distillation,
    run_blogger_url_collection,
)
from app.blogger_distillation.tikhub_client import TikHubError
from app.config import get_settings
from app.models import OperationTask
from app.pipeline import PubSyncPipeline
from app.schemas import XhsPublishPackageCreate
from app.services.ai_service import AIServiceError
from app.services.tenant_service import (
    build_effective_settings,
    get_content_groups,
    get_layout_settings,
    get_profile,
    get_publishing_settings,
    get_tenant,
    get_wechat_account,
)
from app.services.wechat_service import WeChatAPIError
from app.account_audit.service import run_account_audit
from app.benchmark_discovery.service import run_recommendation
from app.skill_optimization.service import run_skill_optimization
from app.xhs_creation.service import generate_xhs_publish_package_draft

from .core import execute_task, get_task, mark_task_running, mark_task_succeeded

logger = logging.getLogger(__name__)


def build_pipeline(db: Session, task_id: str, task_type: str, tenant_id: int) -> PubSyncPipeline:
    tenant = get_tenant(db, tenant_id)
    settings = get_settings()
    publishing = get_publishing_settings(db, tenant)
    return PubSyncPipeline(
        db=db,
        settings=build_effective_settings(settings, publishing),
        task_id=task_id,
        task_type=task_type,
        tenant=tenant,
        profile=get_profile(db, tenant),
        wechat_account=get_wechat_account(db, tenant),
        layout_settings=get_layout_settings(db, tenant),
        publishing_settings=publishing,
        content_groups=get_content_groups(db, tenant, enabled_only=True),
    )


def run_news_fetch_task(task_id: str) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在抓取新闻并进行大模型筛选")
        tenant = get_tenant(db, task.tenant_id)
        created_items = build_pipeline(db, task_id, "news_fetch", tenant.id).run_news_fetch()
        mark_task_succeeded(db, task, f"新闻抓取完成，新增 {len(created_items)} 条")
        logger.info("任务成功：任务ID=%s，类型=新闻抓取，新增=%s", task_id, len(created_items))

    execute_task(task_id, label="新闻抓取", fail_message="新闻抓取失败", work=work, expected=(AIServiceError,))


def run_article_generation_task(task_id: str) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在生成文章，可能需要数分钟")
        tenant = get_tenant(db, task.tenant_id)
        article = build_pipeline(db, task_id, "article_generation", tenant.id).run_article_generation()
        mark_task_succeeded(db, task, "文章生成完成", article_id=article.id)
        logger.info("任务成功：任务ID=%s，类型=文章生成，文章ID=%s", task_id, article.id)

    execute_task(task_id, label="文章生成", fail_message="文章生成失败", work=work, expected=(ValueError, AIServiceError))


def run_blogger_collection_task(
    task_id: str,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
    asr_enabled: bool = False,
    content_types: list[str] | None = None,
    order: str = "top_liked",
    fetch_all: bool = False,
) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在采集小红书样本")
        result = run_blogger_collection(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            blogger_id=blogger_id,
            sample_limit=sample_limit,
            comments_per_post=comments_per_post,
            asr_enabled=asr_enabled,
            content_types=content_types,
            order=order,
            fetch_all=fetch_all,
        )
        mark_task_succeeded(db, task, f"样本采集完成，采集 {result.run.post_count} 条")
        logger.info("任务成功：任务ID=%s，类型=博主样本采集，采集批次ID=%s", task_id, result.run.id)

    execute_task(
        task_id,
        label="博主样本采集",
        fail_message="博主样本采集失败",
        work=work,
        expected=(ValueError, TikHubError),
        cancellable=True,
    )


def run_blogger_url_collection_task(
    task_id: str,
    blogger_id: int,
    urls: list[str],
    comments_per_post: int = 20,
    asr_enabled: bool = False,
) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在按链接定向采集")
        result = run_blogger_url_collection(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            blogger_id=blogger_id,
            urls=urls,
            comments_per_post=comments_per_post,
            asr_enabled=asr_enabled,
        )
        mark_task_succeeded(db, task, f"定向采集完成，采集 {result.run.post_count} 条")
        logger.info("任务成功：任务ID=%s，类型=博主定向采集，采集批次ID=%s", task_id, result.run.id)

    execute_task(
        task_id,
        label="博主定向采集",
        fail_message="博主定向采集失败",
        work=work,
        expected=(ValueError, TikHubError),
        cancellable=True,
    )


def run_blogger_distillation_task(
    task_id: str,
    blogger_id: int,
    post_ids: list[int],
    source: str = "custom",
    snapshot_id: int | None = None,
    mode: str = "A",
) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在基于所选样本蒸馏 Skill")
        result = run_blogger_distillation(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            blogger_id=blogger_id,
            post_ids=post_ids,
            source=source,
            snapshot_id=snapshot_id,
            mode=mode,
        )
        mark_task_succeeded(db, task, f"博主蒸馏完成，等待确认：{result.skill.name}")
        logger.info("任务成功：任务ID=%s，类型=博主蒸馏，运行ID=%s，Skill ID=%s", task_id, result.run.id, result.skill.id)

    def record_failure(db: Session, task_id: str, exc: Exception) -> None:
        task = get_task(db, task_id)
        if task:
            record_task_event(db, task.tenant_id, task_id, "博主蒸馏", "failed", f"博主蒸馏失败：{type(exc).__name__}: {exc}")

    execute_task(
        task_id,
        label="博主蒸馏",
        fail_message="博主蒸馏失败",
        work=work,
        expected=(ValueError, AIServiceError, TikHubError),
        cancellable=True,
        on_unexpected=record_failure,
    )


def run_xhs_package_draft_task(task_id: str, payload: dict) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在生成小红书正文/脚本和素材")
        record_task_event(db, task.tenant_id, task_id, "发布包生成", "running", "开始生成正文/脚本")
        draft_payload = XhsPublishPackageCreate.model_validate(payload)
        draft = generate_xhs_publish_package_draft(db, get_settings(), task.tenant_id, draft_payload, task_id=task_id)
        record_task_event(
            db,
            task.tenant_id,
            task_id,
            "发布包草稿",
            "succeeded",
            "发布包草稿生成完成",
            {"draft": draft},
        )
        mark_task_succeeded(db, task, "小红书发布包草稿生成完成")
        logger.info("任务成功：任务ID=%s，类型=小红书发布包草稿生成", task_id)

    execute_task(
        task_id,
        label="小红书发布包草稿生成",
        fail_message="小红书发布包草稿生成失败",
        work=work,
        expected=(ValueError, AIServiceError),
    )


def run_account_audit_task(task_id: str, payload: dict) -> None:
    kind = "self" if str(payload.get("kind") or "").strip().lower() == "self" else "benchmark"
    subject = "诊断我的" if kind == "self" else "对标诊断"

    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, f"正在{subject}…")
        run = run_account_audit(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            platform=str(payload.get("platform") or "xhs"),
            kind=kind,
            my_blogger_id=int(payload["my_blogger_id"]),
            my_post_ids=[int(x) for x in (payload.get("my_post_ids") or [])],
            benchmark_blogger_id=int(payload["benchmark_blogger_id"]) if payload.get("benchmark_blogger_id") else None,
            benchmark_post_ids=[int(x) for x in (payload.get("benchmark_post_ids") or [])],
        )
        mark_task_succeeded(db, task, f"{subject}完成,评分 {run.score}")
        logger.info("任务成功：任务ID=%s，类型=%s，运行ID=%s", task_id, subject, run.id)

    def record_failure(db: Session, task_id: str, exc: Exception) -> None:
        task = get_task(db, task_id)
        if task:
            record_task_event(db, task.tenant_id, task_id, subject, "failed", f"{subject}失败：{type(exc).__name__}: {exc}")

    execute_task(
        task_id,
        label=subject,
        fail_message=f"{subject}失败",
        work=work,
        expected=(ValueError, AIServiceError),
        on_unexpected=record_failure,
    )


def run_benchmark_recommend_task(task_id: str, payload: dict) -> None:
    subject = "对标推荐"

    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在帮你找对标博主…")
        run = run_recommendation(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            platform=str(payload.get("platform") or "xhs"),
            intent=payload.get("intent") or {},
            my_account_id=int(payload["my_account_id"]) if payload.get("my_account_id") else None,
        )
        mark_task_succeeded(db, task, f"找到 {len(run.candidates)} 个候选对标博主")
        logger.info("任务成功：任务ID=%s，类型=%s，运行ID=%s", task_id, subject, run.id)

    def record_failure(db: Session, task_id: str, exc: Exception) -> None:
        task = get_task(db, task_id)
        if task:
            record_task_event(db, task.tenant_id, task_id, subject, "failed", f"{subject}失败：{type(exc).__name__}: {exc}")

    execute_task(
        task_id,
        label=subject,
        fail_message=f"{subject}失败",
        work=work,
        expected=(ValueError, AIServiceError),
        on_unexpected=record_failure,
    )


def run_skill_optimization_task(task_id: str, payload: dict) -> None:
    subject = "Skill 优化"

    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在优化 Skill…")
        run = run_skill_optimization(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            blogger_id=int(payload["blogger_id"]),
            epochs=int(payload.get("epochs") or 2),
            skill_id=(int(payload["skill_id"]) if payload.get("skill_id") else None),
        )
        if run.status == "failed":
            mark_task_succeeded(db, task, f"优化未完成:{run.error_message or '生成失败,请稍后重试'}")
        else:
            mark_task_succeeded(db, task, f"优化完成:{run.before_score} → {run.after_score}(请在页面确认是否采纳)")
        logger.info("任务成功：任务ID=%s,类型=%s,运行ID=%s,状态=%s", task_id, subject, run.id, run.status)

    def record_failure(db: Session, task_id: str, exc: Exception) -> None:
        task = get_task(db, task_id)
        if task:
            record_task_event(db, task.tenant_id, task_id, subject, "failed", f"{subject}失败：{type(exc).__name__}: {exc}")

    execute_task(
        task_id,
        label=subject,
        fail_message=f"{subject}失败",
        work=work,
        expected=(ValueError, AIServiceError),
        on_unexpected=record_failure,
    )


def run_daily_publish_task(task_id: str) -> None:
    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "正在执行定时抓取、生成和发布流程")
        tenant = get_tenant(db, task.tenant_id)
        publishing = get_publishing_settings(db, tenant)
        article = build_pipeline(db, task_id, "daily_publish", tenant.id).run_daily_publish(
            should_publish=publishing.auto_send_wechat_draft
        )
        if publishing.auto_send_wechat_draft:
            mark_task_succeeded(db, task, "定时任务完成，文章已发送到公众号草稿箱", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=是", task_id, article.id)
        else:
            mark_task_succeeded(db, task, "定时任务完成，文章已生成", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=否", task_id, article.id)

    execute_task(
        task_id,
        label="每日发布",
        fail_message="定时任务失败",
        work=work,
        expected=(ValueError, AIServiceError, WeChatAPIError),
    )


def run_discovery_recall_task(task_id: str, session_id: int) -> None:
    """泛搜索/找相似「找候选」:异步按选中角度/关键词召回,逐角度回报进度,写回会话。"""
    from app.benchmark_discovery import flow
    from app.models import BenchmarkDiscoverySession

    subject = "搜罗候选博主"

    def work(db: Session, task: OperationTask) -> None:
        mark_task_running(db, task, "按角度搜罗候选…")
        session = db.get(BenchmarkDiscoverySession, session_id)
        if not session or session.tenant_id != task.tenant_id:
            mark_task_succeeded(db, task, "会话不存在或已过期")
            return

        def on_progress(label: str, detail: str) -> None:
            # 每搜完一个角度,写一条精确进度(前端 LiveProgress 能看见在动)。
            record_task_event(db, task.tenant_id, task_id, label, "succeeded", detail)

        record_task_event(db, task.tenant_id, task_id, "搜罗候选", "running", "开始")
        summary = flow.run_recall(db, get_settings(), session, on_progress=on_progress)
        record_task_event(db, task.tenant_id, task_id, "核验+筛选", "succeeded",
                          f"新增 {summary.get('added', 0)} 个相关候选" +
                          (f",筛掉 {summary.get('dropped', 0)} 个不相关" if summary.get('dropped') else ""))
        mark_task_succeeded(db, task, session.message)

    execute_task(task_id, label=subject, fail_message=f"{subject}失败", work=work, expected=(ValueError,))
