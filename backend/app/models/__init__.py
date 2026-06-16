"""ORM models, split by domain.

Re-exported here so existing ``from app.models import X`` imports keep working and
so importing this package registers every table on ``Base.metadata``.
"""

from app.models.article import Article, ArticleNewsItem, ArticleStatus
from app.models.audit import AccountAuditRun
from app.models.blogger import (
    BloggerCollectionPost,
    BloggerCollectionRun,
    BloggerDistillationRun,
    BloggerPost,
    BloggerProfile,
    BloggerSkill,
)
from app.models.common import utc_now
from app.models.news import NewsItem, NewsSource, SourceStatus
from app.models.system_config import SystemConfig
from app.models.task import OperationTask, OperationTaskEvent, TaskStatus
from app.models.tenant import Tenant, TenantStatus, User
from app.models.workspace import (
    AppSetting,
    ContentGroup,
    ContentProfile,
    LayoutSettings,
    PublishingSettings,
    WeChatAccount,
)
from app.models.xhs import XhsPublishPackage

__all__ = [
    "utc_now",
    "Tenant",
    "TenantStatus",
    "User",
    "ContentProfile",
    "ContentGroup",
    "WeChatAccount",
    "LayoutSettings",
    "PublishingSettings",
    "AppSetting",
    "NewsItem",
    "NewsSource",
    "SourceStatus",
    "Article",
    "ArticleNewsItem",
    "ArticleStatus",
    "OperationTask",
    "OperationTaskEvent",
    "TaskStatus",
    "SystemConfig",
    "BloggerProfile",
    "BloggerPost",
    "BloggerCollectionRun",
    "BloggerCollectionPost",
    "BloggerDistillationRun",
    "BloggerSkill",
    "XhsPublishPackage",
    "AccountAuditRun",
]
