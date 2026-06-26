"""调度器周期调用的入口:定时发布(``scheduled_workspace_publish``)+ 僵死任务看门狗
(``reap_stale_tasks``)+ 发现会话清理(``reap_discovery_sessions``)。都自建 session、自吞异常,
不让单次失败影响调度器。
"""

import logging
from calendar import monthrange
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.blogger_distillation.service import record_task_event
from app.config import get_settings
from app.database import SessionLocal
from app.models import (
    AppSetting,
    CostEvent,
    OperationTask,
    OperationTaskEvent,
    PublishingSettings,
    TaskStatus,
    Tenant,
    TenantStatus,
)
from app.queue import enqueue

from .core import create_operation_task
from .runners import run_daily_publish_task

logger = logging.getLogger(__name__)


# —— 定时发布(按租户的发布设置,到点触发一次每日发布任务)——
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
    use_queue = get_settings().use_task_queue
    for task_id in task_ids:
        if use_queue:
            enqueue(run_daily_publish_task, task_id)
        else:
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


# —— 僵死任务看门狗(worker 被 OOM/强杀时,任务会一直卡 running,异常处理不会触发)——
STALE_REAP_STATUSES = (TaskStatus.running, TaskStatus.cancel_requested)
STALE_FAIL_MESSAGE = (
    "任务超过 {minutes} 分钟没有任何进展，多半是后台进程因服务器资源不足被中断；"
    "已自动标记为失败。已完成的部分都已保存，可以重新发起（采集是增量的，会自动跳过已采集的内容）。"
)


def reap_stale_tasks_in_session(db: Session, now: datetime, stale_minutes: int) -> list[str]:
    """把「进行中但超过 stale_minutes 没有新进展事件」的任务标记为失败,返回被回收的 task_id。

    判活信号 = 该任务最近一条事件时间(没有事件则退回 updated_at/created_at)。只动 running/cancel_requested,
    不碰 queued(可能只是在排队等单 worker,静默不代表死)。
    """
    cutoff = now - timedelta(minutes=stale_minutes)
    reaped: list[str] = []
    tasks = list(db.scalars(select(OperationTask).where(OperationTask.status.in_(STALE_REAP_STATUSES))))
    for task in tasks:
        # 判活信号取「最近进度事件」与「最近一次计费(LLM/TikHub 调用)」的较晚者。
        # 计费事件每次调用都会写,所以 Skill 优化训练这种「很久不发进度事件、但底层一直在调模型」的
        # 任务不会被误杀;真卡死(连模型都不再调用)时两个时间都旧,才回收。
        last_event = db.scalar(
            select(func.max(OperationTaskEvent.created_at)).where(OperationTaskEvent.task_id == task.id)
        )
        last_cost = db.scalar(
            select(func.max(CostEvent.created_at)).where(CostEvent.task_id == task.id)
        )

        def _aware(dt: datetime | None) -> datetime | None:  # sqlite 可能返回 naive,统一成 UTC 再比较
            return None if dt is None else (dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt)

        candidates = [c for c in (_aware(last_event), _aware(last_cost),
                                  _aware(task.updated_at), _aware(task.created_at)) if c is not None]
        last_activity = max(candidates) if candidates else None
        if last_activity is None or last_activity >= cutoff:
            continue
        msg = STALE_FAIL_MESSAGE.format(minutes=stale_minutes)
        record_task_event(db, task.tenant_id, task.id, "任务中断", "failed", msg)
        task.status = TaskStatus.failed
        task.message = "任务已中断"
        task.error_message = msg
        db.commit()
        reaped.append(task.id)
        logger.warning("回收僵死任务：任务ID=%s，类型=%s，最后活动=%s", task.id, task.task_type, last_activity)
    return reaped


def reap_stale_tasks() -> None:
    """定时入口(无参,自建 session):回收僵死任务。由调度器周期调用。"""
    db = SessionLocal()
    try:
        minutes = int(getattr(get_settings(), "task_stale_minutes", 20) or 20)
        reaped = reap_stale_tasks_in_session(db, datetime.now(timezone.utc), minutes)
        if reaped:
            logger.info("僵死任务看门狗：本轮回收 %s 个任务", len(reaped))
    except Exception:  # noqa: BLE001 - 看门狗自身异常不应影响调度器
        db.rollback()
        logger.exception("僵死任务看门狗执行失败")
    finally:
        db.close()


def reap_discovery_sessions() -> None:
    """定时入口(无参):把空闲过期的发现会话标 expired。"""
    from app.benchmark_discovery.flow import reap_expired_sessions

    db = SessionLocal()
    try:
        n = reap_expired_sessions(db, datetime.now(timezone.utc))
        if n:
            logger.info("发现会话清理：本轮过期 %s 个", n)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("发现会话清理失败")
    finally:
        db.close()
