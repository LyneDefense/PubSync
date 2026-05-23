import logging
from uuid import uuid4

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.models import OperationTask, TaskStatus
from app.services.ai_service import AIServiceError
from app.services.article_service import generate_article_from_selected_news
from app.services.news_service import fetch_latest_news
from app.services.wechat_service import send_article_to_wechat_draft


logger = logging.getLogger(__name__)

TASK_MESSAGES = {
    "news_fetch": "已加入后台抓取任务",
    "article_generation": "已加入后台生成任务",
    "daily_publish": "已加入定时发布任务",
}


def create_operation_task(db: Session, task_type: str, message: str | None = None) -> OperationTask:
    task = OperationTask(
        id=str(uuid4()),
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
        created_items = fetch_latest_news(db)
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
        article = generate_article_from_selected_news(db)
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


def run_daily_publish_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        logger.info("任务开始：任务ID=%s，类型=每日发布", task_id)
        task = get_task(db, task_id)
        if not task:
            return

        settings = get_settings()
        mark_task_running(db, task, "正在执行定时抓取、生成和发布流程")
        fetch_latest_news(db)
        article = generate_article_from_selected_news(db)
        if settings.auto_send_wechat_draft:
            send_article_to_wechat_draft(db, article)
            mark_task_succeeded(db, task, "定时任务完成，文章已发送到公众号草稿箱", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=是", task_id, article.id)
        else:
            mark_task_succeeded(db, task, "定时任务完成，文章已生成", article_id=article.id)
            logger.info("任务成功：任务ID=%s，类型=每日发布，文章ID=%s，已发送公众号草稿=否", task_id, article.id)
    except (ValueError, AIServiceError) as exc:
        logger.warning("任务失败：任务ID=%s，类型=每日发布，错误=%s", task_id, exc)
        mark_task_failed_by_id(db, task_id, "定时任务失败", str(exc))
    except Exception as exc:
        logger.exception("任务异常：任务ID=%s，类型=每日发布", task_id)
        mark_task_failed_by_id(db, task_id, "定时任务失败", f"{type(exc).__name__}: {exc}")
        raise
    finally:
        db.close()


def scheduled_daily_publish() -> None:
    db = SessionLocal()
    try:
        task = create_operation_task(db, "daily_publish")
        task_id = task.id
    finally:
        db.close()
    run_daily_publish_task(task_id)


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


def mark_task_failed_by_id(db: Session, task_id: str, message: str, error_message: str) -> None:
    db.rollback()
    task = get_task(db, task_id)
    if not task:
        return
    task.status = TaskStatus.failed
    task.message = message
    task.error_message = error_message
    db.commit()
