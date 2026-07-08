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
    # 用户对该博主的备注(自己写);与平台主页简介 signature 分开,不混用。
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 平台主页简介/个性签名(从 user_info 解析,刷新资料时更新);只读展示。
    signature: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 账号级获赞与收藏总数(user_info,覆盖全部笔记,含未入池;解析不到为 NULL)。与池内求和区分。
    liked_collected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 内容标签:JSON 数组,元素 {"name": str, "source": "auto"|"manual"}。
    # auto=采集时 LLM 提炼(每次重算替换),manual=用户手填(永久保留)。
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    is_favorite: Mapped[bool] = mapped_column(default=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_distilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 笔记池(档案物理层)同步状态:最后一次列表同步时间;是否翻到列表底部(含第一篇,轨迹才算完整)。
    pool_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pool_reached_end: Mapped[bool] = mapped_column(default=False, server_default="false")
    # 爆文归因(LLM,按钮触发):{"generated_at", "hypotheses": [...], "summary"};空=未运行。
    attribution_json: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 运营习惯事实模块(建档算):发布节奏/模态偏好/体裁分布/评论引导(博主自身内容)/博主回复习惯。
    # 事实主体在此;蒸馏解读另存于最新蒸馏 report_json,前端合并展示。空=未建档。
    operating_habits_json: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 合规体检(建档规则扫描):{"grade","score","hits":[...],"coverage":{...},"generated_at"};空=未扫描。
    compliance_json: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 构建互斥锁:进行中的建档/池同步任务 id;任务结束(含失败)清空。配合任务状态自愈。
    build_task_id: Mapped[str] = mapped_column(String(36), nullable=False, default="", server_default="")
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
    # 模态判定置信来源:platform(图文)/density(字·秒)/chars(无时长回退)/llm(语义裁决)/unknown。空=旧数据未判。
    content_subtype_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="", server_default="")
    hashtags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    cover_url: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    media_urls_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    transcript_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 视频时长(秒),来自 ASR 结果(腾讯 ASR 已 ffprobe);用于 content_subtype 的「字/秒」密度判定。
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    asr_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_required")
    asr_error: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 视觉层:图内逐字 OCR + 结构化视觉摘要(封面话术/版式/风格/信息点),与 transcript_text 对称。
    image_text: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    visual_digest: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    vision_status: Mapped[str] = mapped_column(String(30), nullable=False, default="not_required", server_default="not_required")
    vision_error: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    vision_image_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 视频档案(分层结构化 JSON):L0 采集免费(时长/口播浓度/封面)、L1 镜头切分、L2 代表帧;取代 content_subtype 作为「门」。
    video_profile: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # 从 video_profile 派生的展示/筛选标签 JSON:{narration_level,on_camera,pace,video_kind}。可重算,不重采。
    video_tags: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorite_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    share_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 浏览量(列表卡自带);>0 时可算互动率。
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 详情级别:list=仅列表数据(标题/时间/互动,全量笔记池);full=抓过详情(正文/转写/图文理解/评论)。
    # 只升不降;存量行都走过详情管线,默认 full。
    detail_level: Mapped[str] = mapped_column(String(10), nullable=False, default="full", server_default="full", index=True)
    # 列表卡携带的 xsec_token,list 级行日后升级详情时用(详情接口需要它)。
    xsec_token: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    comments_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    raw_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    # 生命周期:active=在架,delisted=已下架(博主删了,仅在「翻到底对账」时标记),
    # preview=对标搜寻"深看"时抓的试采笔记(未采纳则清理,不进蒸馏)。
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active", index=True)
    # 最近一次出现在主页列表里的时间;下架对账用。
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 下架对账:连续多少次「完整爬取」里没出现。达到阈值才标 delisted(防翻页不稳导致误杀)。
    missed_crawl_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    # 稳定规范键:小红书 biz_id / 抖音 aweme_id。external_id(note_id) 会随端点漂移,note_key 跨次稳定,
    # 用作权威去重键(upsert 按它覆盖),空则回退 external_id。
    note_key: Mapped[str] = mapped_column(String(64), nullable=False, default="", server_default="", index=True)
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
