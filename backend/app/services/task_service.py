import logging
from calendar import monthrange
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.blogger_distillation.service import (
    DistillationCancelled,
    record_task_event,
    run_blogger_collection,
    run_blogger_distillation,
)
from app.blogger_distillation.tikhub_client import TikHubError
from app.database import SessionLocal
from app.harness import PubSyncHarness
from app.models import AppSetting, OperationTask, PublishingSettings, TaskStatus, Tenant, TenantStatus
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


logger = logging.getLogger(__name__)

TASK_MESSAGES = {
    "news_fetch": "已加入后台抓取任务",
    "article_generation": "已加入后台生成任务",
    "daily_publish": "已加入定时发布任务",
    "blogger_collection": "已加入博主样本采集任务",
    "blogger_distillation": "已加入博主蒸馏任务",
}


def create_operation_task(db: Session, task_type: str, tenant_id: int, message: str | None = None) -> OperationTask:
    task = OperationTask(
        id=str(uuid4()),
        tenant_id=tenant_id,
        task_type=task_type,
        status=TaskStatus.queued,
        message=message or TASK_MESSAGES.get(task_type, "已加入后台任务"),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def run_news_fetch_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=新闻抓取", task_id)
        task = get_task(db, task_id)
        if not task:
            return

        mark_task_running(db, task, "正在抓取新闻并进行大模型筛选")
        tenant = get_tenant(db, task.tenant_id)
        created_items = build_harness(db, task_id, "news_fetch", tenant.id).run_news_fetch()
        mark_task_succeeded(db, task, f"新闻抓取完成，新增 {len(created_items)} 条")
        logger.info("任务成功：任务ID=%s，类型=新闻抓取，新增=%s", task_id, len(created_items))
    except AIServiceError as exc:
        logger.warning("任务失败：任务ID=%s，类型=新闻抓取，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "新闻抓取失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=新闻抓取", task_id)
        mark_task_failed_by_id(db, task_id, "新闻抓取失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def run_article_generation_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=文章生成", task_id)
        task = get_task(db, task_id)
        if not task:
            return

        mark_task_running(db, task, "正在生成文章，可能需要数分钟")
        tenant = get_tenant(db, task.tenant_id)
        article = build_harness(db, task_id, "article_generation", tenant.id).run_article_generation()
        mark_task_succeeded(db, task, "文章生成完成", article_id=article.id)
        logger.info("任务成功：任务ID=%s，类型=文章生成，文章ID=%s", task_id, article.id)
    except (ValueError, AIServiceError) as exc:
        logger.warning("任务失败：任务ID=%s，类型=文章生成，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "文章生成失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=文章生成", task_id)
        mark_task_failed_by_id(db, task_id, "文章生成失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def run_blogger_collection_task(
    task_id: str,
    blogger_id: int,
    sample_limit: int = 50,
    comments_per_post: int = 20,
    asr_enabled: bool = False,
) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=博主样本采集，博主ID=%s", task_id, blogger_id)
        task = get_task(db, task_id)
        if not task:
            return

        if task.status == TaskStatus.cancel_requested:
            mark_task_cancelled(db, task, "博主样本采集已停止")
            return
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
        )
        mark_task_succeeded(db, task, f"样本采集完成，采集 {result.run.post_count} 条")
        logger.info("任务成功：任务ID=%s，类型=博主样本采集，采集批次ID=%s", task_id, result.run.id)
    except DistillationCancelled as exc:
        logger.info("任务停止：任务ID=%s，类型=博主样本采集，原因=%s", task_id, exc)
        mark_task_cancelled_by_id(db, task_id, "博主样本采集已停止", str(exc))
    except (ValueError, TikHubError) as exc:
        logger.warning("任务失败：任务ID=%s，类型=博主样本采集，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "博主样本采集失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=博主样本采集", task_id)
        mark_task_failed_by_id(db, task_id, "博主样本采集失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def run_blogger_distillation_task(
    task_id: str,
    blogger_id: int,
    collection_run_id: int,
) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=博主蒸馏，博主ID=%s", task_id, blogger_id)
        task = get_task(db, task_id)
        if not task:
            return

        if task.status == TaskStatus.cancel_requested:
            mark_task_cancelled(db, task, "博主蒸馏已停止")
            return
        mark_task_running(db, task, "正在基于已采集样本蒸馏 Skill")
        result = run_blogger_distillation(
            db=db,
            settings=get_settings(),
            task_id=task_id,
            tenant_id=task.tenant_id,
            blogger_id=blogger_id,
            collection_run_id=collection_run_id,
        )
        mark_task_succeeded(db, task, f"博主蒸馏完成，生成 Skill：{result.skill.name}")
        logger.info("任务成功：任务ID=%s，类型=博主蒸馏，运行ID=%s，Skill ID=%s", task_id, result.run.id, result.skill.id)
    except DistillationCancelled as exc:
        logger.info("任务停止：任务ID=%s，类型=博主蒸馏，原因=%s", task_id, exc)
        mark_task_cancelled_by_id(db, task_id, "博主蒸馏已停止", str(exc))
    except (ValueError, AIServiceError, TikHubError) as exc:
        logger.warning("任务失败：任务ID=%s，类型=博主蒸馏，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "博主蒸馏失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=博主蒸馏", task_id)
        try:
            task = get_task(db, task_id)
            if task:
                record_task_event(db, task.tenant_id, task_id, "博主蒸馏", "failed", f"博主蒸馏失败：{type(exc).__name__}: {exc}")
        except Exception:
            logger.exception("记录博主蒸馏失败事件失败：任务ID=%s", task_id)
        mark_task_failed_by_id(db, task_id, "博主蒸馏失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def run_daily_publish_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=每日发布", task_id)
        task = get_task(db, task_id)
        if not task:
            return

        mark_task_running(db, task, "正在执行定时抓取、生成和发布流程")
        tenant = get_tenant(db, task.tenant_id)
        publishing = get_publishing_settings(db, tenant)
        article = build_harness(db, task_id, "daily_publish", tenant.id).run_daily_publish(
            should_publish=publishing.auto_send_wechat_draft
        )
        if publishing.auto_send_wechat_draft:
            mark_task_succeeded(db, task, "定时任务完成，文章已发送到公众号草稿箱", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=是", task_id, article.id)
        else:
            mark_task_succeeded(db, task, "定时任务完成，文章已生成", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=否", task_id, article.id)
    except (ValueError, AIServiceError, WeChatAPIError) as exc:
        logger.warning("任务失败：任务ID=%s，类型=每日发布，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "定时任务失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=每日发布", task_id)
        mark_task_failed_by_id(db, task_id, "定时任务失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def scheduled_workspace_publish() -> None:
    db = SessionLocal()
    try:
        now = datetime.now()
        task_ids: list[str] = []
        rows = db.execute(
            select(Tenant, PublishingSettings)
            .join(PublishingSettings, PublishingSettings.tenant_id == Tenant.id)
            .where(Tenant.status == TenantStatus.active, PublishingSettings.daily_publish_enabled.is_(True))
        ).all()
        for tenant, publishing in rows:
            if not should_run_schedule(publishing, now):
                continue
            marker_key = f"tenant:{tenant.id}:last_scheduled_publish_at"
            schedule_key = schedule_marker_value(publishing, now)
            marker = db.get(AppSetting, marker_key)
            if marker and marker.value == schedule_key:
                continue
            task = create_operation_task(db, "daily_publish", tenant_id=tenant.id)
            db.merge(AppSetting(key=marker_key, tenant_id=tenant.id, value=schedule_key))
            db.commit()
            task_ids.append(task.id)
    finally:
        db.close()
    for task_id in task_ids:
        run_daily_publish_task(task_id)


def should_run_schedule(publishing: PublishingSettings, now: datetime) -> bool:
    if publishing.publish_time_hour != now.hour or publishing.publish_time_minute != now.minute:
        return False
    frequency = publishing.publish_frequency or "daily"
    if frequency == "weekly":
        return publishing.publish_weekday == now.isoweekday()
    if frequency == "monthly":
        target_day = min(publishing.publish_month_day, monthrange(now.year, now.month)[1])
        return now.day == target_day
    return True


def schedule_marker_value(publishing: PublishingSettings, now: datetime) -> str:
    frequency = publishing.publish_frequency or "daily"
    if frequency == "weekly":
        year, week, _ = now.isocalendar()
        return f"weekly:{year}-{week:02d}:{publishing.publish_time_hour:02d}:{publishing.publish_time_minute:02d}"
    if frequency == "monthly":
        return f"monthly:{now.year}-{now.month:02d}:{publishing.publish_time_hour:02d}:{publishing.publish_time_minute:02d}"
    return f"daily:{now.strftime('%Y-%m-%d')}:{publishing.publish_time_hour:02d}:{publishing.publish_time_minute:02d}"


def build_harness(db: Session, task_id: str, task_type: str, tenant_id: int) -> PubSyncHarness:
    tenant = get_tenant(db, tenant_id)
    settings = get_settings()
    publishing = get_publishing_settings(db, tenant)
    return PubSyncHarness(
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


def get_task(db: Session, task_id: str) -> OperationTask | None:
    return db.get(OperationTask, task_id)


def mark_task_running(db: Session, task: OperationTask, message: str) -> None:
    task.status = TaskStatus.running
    task.message = message
    task.error_message = None
    db.commit()


def mark_task_succeeded(db: Session, task: OperationTask, message: str, article_id: int | None = None) -> None:
    task.status = TaskStatus.succeeded
    task.message = message
    task.article_id = article_id
    task.error_message = None
    db.commit()


def request_task_cancel(db: Session, task: OperationTask) -> None:
    if task.status in {TaskStatus.succeeded, TaskStatus.failed, TaskStatus.cancelled}:
        return
    task.status = TaskStatus.cancel_requested
    task.message = "正在请求停止任务，当前步骤结束后会安全退出"
    db.commit()


def mark_task_cancelled(db: Session, task: OperationTask, message: str, error_message: str | None = None) -> None:
    task.status = TaskStatus.cancelled
    task.message = message
    task.error_message = error_message
    db.commit()


def mark_task_cancelled_by_id(db: Session, task_id: str, message: str, error_message: str | None = None) -> None:
    db.rollback()
    task = get_task(db, task_id)
    if not task:
        return
    mark_task_cancelled(db, task, message, error_message)


def mark_task_failed_by_id(db: Session, task_id: str, message: str, error_message: str) -> None:
    db.rollback()
    task = get_task(db, task_id)
    if not task:
        return
    task.status = TaskStatus.failed
    task.message = message
    task.error_message = error_message
    db.commit()
