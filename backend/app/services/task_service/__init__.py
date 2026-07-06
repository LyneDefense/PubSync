"""后台任务编排层。原先是单文件 task_service.py(640+ 行),按职责拆成三块:

- :mod:`.core`        —— 任务生命周期原语(建任务 / execute_task 执行壳 / 状态流转)。
- :mod:`.runners`     —— 各业务的 ``run_*_task`` 入口 + 公众号流水线装配 ``build_pipeline``。
- :mod:`.maintenance` —— 调度器周期任务:定时发布 + 僵死任务看门狗。

这里把对外公开的名字原样再导出,调用方仍可 ``from app.services.task_service import xxx``(保持兼容)。
"""

from .core import (
    TASK_MESSAGES,
    create_operation_task,
    execute_task,
    get_task,
    mark_task_cancelled,
    mark_task_cancelled_by_id,
    mark_task_failed_by_id,
    mark_task_running,
    mark_task_succeeded,
    request_task_cancel,
)
from .maintenance import (
    reap_stale_tasks,
    reap_stale_tasks_in_session,
    schedule_marker_value,
    scheduled_workspace_publish,
    should_run_schedule,
)
from .runners import (
    build_pipeline,
    run_account_audit_task,
    run_appraisal_task,
    run_article_generation_task,
    run_benchmark_recommend_task,
    run_blogger_collection_task,
    run_blogger_distillation_task,
    run_blogger_dossier_task,
    run_blogger_pool_sync_task,
    run_blogger_redistill_task,
    run_blogger_url_collection_task,
    run_daily_publish_task,
    run_news_fetch_task,
    run_xhs_package_draft_task,
)

__all__ = [
    "TASK_MESSAGES",
    "create_operation_task",
    "execute_task",
    "get_task",
    "mark_task_cancelled",
    "mark_task_cancelled_by_id",
    "mark_task_failed_by_id",
    "mark_task_running",
    "mark_task_succeeded",
    "request_task_cancel",
    "build_pipeline",
    "run_account_audit_task",
    "run_appraisal_task",
    "run_article_generation_task",
    "run_benchmark_recommend_task",
    "run_blogger_collection_task",
    "run_blogger_distillation_task",
    "run_blogger_dossier_task",
    "run_blogger_pool_sync_task",
    "run_blogger_redistill_task",
    "run_blogger_url_collection_task",
    "run_daily_publish_task",
    "run_news_fetch_task",
    "run_xhs_package_draft_task",
    "reap_stale_tasks",
    "reap_stale_tasks_in_session",
    "schedule_marker_value",
    "scheduled_workspace_publish",
    "should_run_schedule",
]
