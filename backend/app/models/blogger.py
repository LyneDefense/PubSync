import json
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.common import utc_now
from app.models.task import OperationTask
from app.models.tenant import Tenant


class BloggerProfile(Base):
    __tablename__ = "blogger_profiles"
    __table_args__ = (UniqueConstraint("tenant_id", "homepage_url", name="uq_blogger_profiles_tenant_homepage"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    # 账号类型:benchmark=对标博主(默认),mine=我的账号。
    account_type: Mapped[str] = mapped_column(String(20), nullable=False, default="benchmark", index=True)
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    homepage_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    avatar_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    follower_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 平台侧笔记/作品总数(从 user_info 解析,解析不到为 NULL)。与"已采集 N 条(sample_count)"区分。
    note_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    niche: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 内容标签:JSON 数组,元素 {"name": str, "source": "auto"|"manual"}。
    # auto=采集时 LLM 提炼(每次重算替换),manual=用户手填(永久保留)。
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    is_favorite: Mapped[bool] = mapped_column(default=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_distilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    tenant: Mapped[Tenant] = relationship()

    @property
    def tags(self) -> list[dict[str, str]]:
        """解析 tags_json 为 [{"name", "source"}],供序列化使用。"""
        try:
            data = json.loads(self.tags_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
        return [t for t in data if isinstance(t, dict) and t.get("name")]


class BloggerPost(Base):
    __tablename__ = "blogger_posts"
    __table_args__ = (UniqueConstraint("tenant_id", "blogger_id", "external_id", name="uq_blogger_posts_external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(String(30), nullable=False, default="xhs")
    external_id: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="image")
    # 内容模态细分(可扩展枚举):image_text/talking_video/visual_video/unknown;
    # 预留 article/article_with_image 给公众号。采集时按 content_type + 转写密度启发式打标。
    content_subtype: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown", server_default="unknown", index=True)
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    media_urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    asr_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_required")
    asr_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    share_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    comments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 生命周期:active=在架,delisted=已下架(博主删了,仅在「翻到底对账」时标记)。
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active", index=True)
    # 最近一次出现在主页列表里的时间;下架对账用。
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerCollectionRun(Base):
    __tablename__ = "blogger_collection_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    sample_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    comments_per_post: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    asr_enabled: Mapped[bool] = mapped_column(default=False)
    post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hot_post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_min_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_max_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    summary_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerCollectionPost(Base):
    __tablename__ = "blogger_collection_posts"
    __table_args__ = (UniqueConstraint("collection_run_id", "post_id", name="uq_blogger_collection_posts"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    collection_run_id: Mapped[int] = mapped_column(ForeignKey("blogger_collection_runs.id"), nullable=False, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("blogger_posts.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    collection_run: Mapped[BloggerCollectionRun] = relationship()
    post: Mapped[BloggerPost] = relationship()
    blogger: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerDistillationRun(Base):
    __tablename__ = "blogger_distillation_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    collection_run_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_collection_runs.id"), nullable=True, index=True)
    # 蒸馏选材来源:自定义蒸馏指向快照(自动蒸馏为 NULL);selection_json 记录本次实际蒸的 post_ids 与来源 auto/custom。
    snapshot_id: Mapped[int | None] = mapped_column(ForeignKey("blogger_snapshots.id"), nullable=True, index=True)
    selection_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}", server_default="{}")
    task_id: Mapped[str | None] = mapped_column(ForeignKey("operation_tasks.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    hot_post_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tikhub_estimated_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_min_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    tikhub_cost_max_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    report_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    report_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    collection_run: Mapped[BloggerCollectionRun | None] = relationship()
    task: Mapped[OperationTask | None] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerSkill(Base):
    __tablename__ = "blogger_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("blogger_distillation_runs.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    skill_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    # 该 skill 的内容模态成分(JSON 数组):如 ["image_text","talking_video"];["__all__"]=通用。
    scope_json: Mapped[str] = mapped_column(Text, nullable=False, default='["__all__"]', server_default='["__all__"]')
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    run: Mapped[BloggerDistillationRun] = relationship()
    tenant: Mapped[Tenant] = relationship()


class BloggerSnapshot(Base):
    """蒸馏选材快照:用户自定义蒸馏时勾选的一组笔记,命名留存,可复用/回看。"""

    __tablename__ = "blogger_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), nullable=False, index=True)
    blogger_id: Mapped[int] = mapped_column(ForeignKey("blogger_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    # 选中的 BloggerPost id 列表(JSON 数组)。
    post_ids_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)

    blogger: Mapped[BloggerProfile] = relationship()
    tenant: Mapped[Tenant] = relationship()

    @property
    def post_ids(self) -> list[int]:
        try:
            data = json.loads(self.post_ids_json or "[]")
        except (json.JSONDecodeError, TypeError):
            return []
        return [int(x) for x in data if isinstance(x, (int, str)) and str(x).isdigit()]

    @property
    def post_count(self) -> int:
        return len(self.post_ids)
