from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BloggerProfileCreate(BaseModel):
    platform: str = Field(default="xhs", pattern="^(xhs|douyin)$")
    account_type: str = Field(default="benchmark", pattern="^(benchmark|mine)$")
    external_id: str | None = Field(default=None, max_length=200)
    display_name: str = Field(min_length=1, max_length=160)
    homepage_url: str = Field(min_length=1, max_length=1000)
    avatar_url: str = Field(default="", max_length=1000)
    follower_count: int = Field(default=0, ge=0)
    niche: str = Field(default="", max_length=160)
    description: str = ""


class BloggerProfileUpdate(BaseModel):
    external_id: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    homepage_url: str | None = Field(default=None, min_length=1, max_length=1000)
    avatar_url: str | None = Field(default=None, max_length=1000)
    follower_count: int | None = Field(default=None, ge=0)
    niche: str | None = Field(default=None, max_length=160)
    description: str | None = None
    # 手动标签(逗号/列表)。传则替换全部 manual 标签,自动标签保留。
    tags: list[str] | None = Field(default=None, max_length=20)


class BloggerFavoriteUpdate(BaseModel):
    is_favorite: bool


class BloggerProfileRead(BaseModel):
    id: int
    tenant_id: int
    platform: str
    account_type: str
    external_id: str | None
    display_name: str
    homepage_url: str
    avatar_url: str
    follower_count: int
    note_total: int | None = None
    liked_collected_count: int | None = None
    niche: str
    description: str
    signature: str = ""
    tags: list[dict] = []
    is_favorite: bool
    sample_count: int
    last_distilled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerSearchResultRead(BaseModel):
    platform: str
    external_id: str
    display_name: str
    homepage_url: str
    avatar_url: str
    description: str
    follower_count: int
    raw: dict
    # 火爆度速览(0-100,仅按粉丝数粗算,免费);评估按钮才跑完整四项指标。
    quick_popularity: float = 0


class BloggerDistillRequest(BaseModel):
    # auto=自动蒸馏(系统预设:高赞 top-N);custom=自定义(选快照 或 手选 N 篇)。
    source: str = Field(default="auto", pattern="^(auto|custom)$")
    # custom 手选笔记 id(与 snapshot_id 二选一;手选会自动存一个快照)。
    post_ids: list[int] = Field(default_factory=list)
    # custom 复用已有快照。
    snapshot_id: int | None = None
    # 自动存快照时的命名(留空则后端自动生成)。
    snapshot_name: str = Field(default="", max_length=160)
    # A=拆解对标博主（默认）；B=诊断我的账号。
    mode: str = Field(default="A")


class BloggerSnapshotCreate(BaseModel):
    name: str = Field(default="", max_length=160)
    post_ids: list[int] = Field(min_length=1)


class BloggerSnapshotUpdate(BaseModel):
    # 改名 / 重选笔记,二者可单独或一起传。
    name: str | None = Field(default=None, max_length=160)
    post_ids: list[int] | None = None


class BloggerSnapshotRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    name: str
    post_ids: list[int]
    post_count: int
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# —— 智能选材:按需求让大模型给博主笔记打相关度分,帮用户建快照 ——
class SnapshotSuggestRequest(BaseModel):
    need: str = Field(default="", max_length=300)


class SnapshotSuggestItem(BaseModel):
    post_id: int
    score: int  # 相关度 0-100(前端据此预勾选 + 一键放宽/自动补)
    reason: str = ""


class SnapshotSuggestResult(BaseModel):
    suggested_name: str = ""
    items: list[SnapshotSuggestItem] = Field(default_factory=list)  # 覆盖所有候选笔记,按分数降序


class CollectEstimate(BaseModel):
    sample_limit: int
    comments_per_post: int
    request_estimate: int
    # 本次采集会顺带"补采"(补图片理解/转写)的存量笔记数(上限估算,DB 计数);前端据此>阈值弹确认。
    backfill_pending: int = 0
    cost_usd: float
    cost_usd_min: float
    cost_usd_max: float


class BloggerCollectRequest(BaseModel):
    sample_limit: int = Field(default=50, ge=5, le=200)
    comments_per_post: int = Field(default=20, ge=0, le=100)
    # ASR 已改为后台全局控制,采集请求不再携带 asr 开关。
    # 拉取范围:image=图文,video=视频;默认全部。仅这两类(口播细分在采集后判定)。
    content_types: list[str] = Field(default_factory=lambda: ["image", "video"])
    # 选材排序:top_liked=高赞优先(默认),latest=最新优先,smart=建档升详情(中位数+最近+爆文保底)。
    order: str = Field(default="top_liked", pattern="^(top_liked|latest|smart)$")
    # 数量:False=取 sample_limit 条,True=全部到系统上限。
    fetch_all: bool = False
    # 是否给存量笔记补采(补图片理解/转写)。False=只采新增的 N 条,不回填(用户在大回填确认框选了"否"时)。
    backfill: bool = True


class BloggerUrlCollectRequest(BaseModel):
    # 粘贴的笔记链接(一行一个);兜底定向采集。ASR 由后台全局控制,不再随请求携带。
    urls: list[str] = Field(min_length=1, max_length=20)
    comments_per_post: int = Field(default=20, ge=0, le=100)


class BloggerPostsDeleteRequest(BaseModel):
    post_ids: list[int]


class BloggerPostRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    platform: str
    external_id: str
    url: str
    title: str
    body_text: str
    content_type: str
    content_subtype: str
    hashtags_json: str
    cover_url: str
    media_urls_json: str
    transcript_text: str
    asr_status: str
    asr_error: str
    image_text: str = ""
    visual_digest: str = ""
    vision_status: str = "not_required"
    vision_image_count: int = 0
    published_at: datetime | None
    like_count: int
    favorite_count: int
    comment_count: int
    share_count: int
    view_count: int = 0
    detail_level: str = "full"
    score: float
    comments_json: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerCollectionRunRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    task_id: str | None
    status: str
    sample_limit: int
    comments_per_post: int
    asr_enabled: bool
    post_count: int
    hot_post_count: int
    comment_count: int
    tikhub_request_count: int
    tikhub_estimated_cost_usd: float
    tikhub_cost_min_usd: float
    tikhub_cost_max_usd: float
    summary_json: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerDistillationRunRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    collection_run_id: int | None
    snapshot_id: int | None = None
    selection_json: str = "{}"
    task_id: str | None
    status: str
    sample_count: int
    hot_post_count: int
    comment_count: int
    tikhub_request_count: int
    tikhub_estimated_cost_usd: float
    tikhub_cost_min_usd: float
    tikhub_cost_max_usd: float
    report_json: str
    report_html: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BloggerSkillRead(BaseModel):
    id: int
    tenant_id: int
    blogger_id: int
    run_id: int
    name: str
    description: str
    skill_markdown: str
    scope_json: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================ 博主档案(Dossier) ============================

class DossierPoolInfo(BaseModel):
    total: int
    note_total: int | None = None
    full_count: int
    list_count: int
    synced_at: datetime | None
    reached_end: bool


class DossierPortrait(BaseModel):
    """一份创作画像(active skill)+ 过时判定。过时≠失效,照常可用。"""

    skill_id: int
    run_id: int
    name: str
    distilled_at: datetime | None
    sample_count: int
    snapshot_id: int | None
    snapshot_name: str
    lanes: list[str]
    new_posts_since: int
    stale: bool


class DossierBuilding(BaseModel):
    task_id: str
    status: str
    message: str


class BloggerDossierRead(BaseModel):
    """档案页聚合读:物理层(池)+ 分析层(统计/轨迹/受众需求)+ 画像 + 构建状态。"""

    blogger_id: int
    pool: DossierPoolInfo
    stats: dict | None
    habits: dict | None = None
    compliance: dict | None = None
    trajectory: dict | None
    audience: dict | None = None
    portraits: list[DossierPortrait]
    building: DossierBuilding | None


class DossierPoolSyncRequest(BaseModel):
    mode: str = Field(default="incremental", pattern="^(incremental|full)$")
