from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pubsync:pubsync@localhost:5432/pubsync"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    admin_username: str = "admin"
    admin_password: str = "change_me"
    auth_secret: str = ""
    session_hours: int = 24
    # 后台运行时配置中密钥(API key 等)落库时的 Fernet 加密钥。留空则由 auth_secret 派生;
    # auth_secret 也为空时,后台拒绝保存密钥类配置(fail-safe,本地默认即如此)。
    config_encryption_key: str = ""
    use_task_queue: bool = False
    redis_url: str = "redis://localhost:6379/0"
    task_queue_name: str = "pubsync"
    task_job_timeout_seconds: int = 3600
    llm_provider: str = "openai"
    image_provider: str = "openai"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_text_model: str = "gpt-4.1"
    openai_image_model: str = "gpt-image-1"
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_api_key: str = ""
    minimax_text_model: str = "MiniMax-M2.7"
    minimax_image_model: str = "image-01"
    # Anthropic / Claude(文本供应商可在管理后台切换;无图像生成,图像仍走 openai/minimax)。
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_api_key: str = ""
    anthropic_text_model: str = "claude-sonnet-4-6"
    anthropic_version: str = "2023-06-01"
    anthropic_max_tokens: int = 8000
    # 博主蒸馏单独的文本模型（留空=用上面的 *_text_model）。蒸馏对推理要求更高，
    # 可在此指向更强的模型（如更高档的 OpenAI/MiniMax 模型）以提升蒸馏质量。
    distill_text_model: str = ""
    # 采集后自动给博主打内容标签（LLM 语义提炼）。每次采集多一次 LLM 调用，可在此关闭以省成本。
    blogger_auto_tag_enabled: bool = True
    blogger_tag_model: str = ""  # 留空=用 distill_text_model 或默认文本模型
    blogger_tag_max: int = 6
    # 内容模态细分:视频转写字数 >= 此阈值判为「口播视频」,否则「非口播视频」。
    talking_video_min_transcript_chars: int = 200
    # 蒸馏时每个被选模态的最低样本数,不足则拒绝(避免样本太少蒸出垃圾)。
    distill_min_samples_per_subtype: int = 5
    # 蒸馏选材:最低样本硬下限(<此值拒绝)、软建议值(界面提示)、自动蒸馏取高赞 top-N。
    distill_min_samples: int = 8
    distill_recommend_samples: int = 15
    # 博主诊断:诊断前确保的最少笔记数(不够自动补采)+ 打分采样篇数。
    appraisal_min_samples: int = 20
    appraisal_sample_size: int = 30
    blogger_auto_distill_top_n: int = 30
    # 候选翻页:动态翻页的安全上限(最多翻这么多条候选,防超大号无限翻);只翻列表不抓详情,成本低。
    # 最新优先:翻到"没采过的够 N 条"就停;高赞优先:翻到底或到此上限再排序。系统决定,用户端不暴露。
    candidate_pool_cap: int = 600
    # 下架对账:某笔记连续这么多次「完整爬取」都没出现才标下架(小红书翻页返回不稳,单次缺失不算)。
    delist_after_consecutive_misses: int = 2
    # 自动下架对账总开关。默认关:小红书 note_id 随端点漂移,可靠下架需逐条抓详情拿 biz_id,代价大且误杀风险高;
    # 真删笔记很少,宁可全留也不误杀。需要时再人工/专门流程处理。
    blogger_auto_delist_enabled: bool = False
    # 合成循环（蒸馏）：质量不达标时自我修订的最大次数、达标阈值、是否启用推理型评审。
    synthesis_max_revise_iterations: int = 1
    synthesis_min_quality_score: int = 80
    synthesis_llm_critic_enabled: bool = True
    # 对标博主搜寻(智能推荐/单博主评分):综合分四项权重 + 候选池上限 + 列表取数 + 搜索词扩展数 + 活跃度阈值。
    benchmark_weight_relevance: float = 0.4
    benchmark_weight_learnability: float = 0.25
    benchmark_weight_popularity: float = 0.25
    benchmark_weight_transferability: float = 0.1
    benchmark_candidate_pool_cap: int = 12
    benchmark_list_sample: int = 12
    benchmark_search_terms_max: int = 5
    benchmark_inactive_days: int = 60
    # 泛搜索(发现会话)：每次「找候选」追加上限(小批)、搜索翻页深度、「挖干」阈值、
    # 候选池累计上限、会话空闲过期小时数。
    discovery_candidate_cap: int = 12        # 核验后展示上限
    discovery_prevet_cap: int = 15           # 核验前的候选上限(广召回先拉这么多,再逐个核验)
    discovery_recent_notes: int = 8          # 核验时取每个候选近期几条笔记标题
    discovery_relevance_floor: int = 30      # LLM 相关度低于此 → 明显不相关,剔除
    discovery_vet_concurrency: int = 5       # 核验时并发取数,别一个个串行等
    discovery_search_pages: int = 2
    discovery_dryup_threshold: int = 3
    discovery_pool_cap: int = 60
    discovery_session_ttl_hours: int = 2
    # 角度收窄(领域 → 细分领域,agent 迭代推荐直到选够 target)。
    discovery_angle_target: int = 3          # 建议选几个细分角度
    discovery_angle_batch: int = 4           # agent 每轮出几个
    discovery_angle_max_rounds: int = 4      # agent 最多出几轮(防空转)
    discovery_angle_timeout_seconds: int = 45  # MiniMax 推角度暖机后约 15s,冷启动更慢,留足别动不动退规则
    discovery_directions_max: int = 10       # 首批角度上限
    # AI 创作的合成循环参数（与蒸馏独立调参）。
    creation_max_revise_iterations: int = 1
    creation_min_quality_score: int = 80
    creation_llm_critic_enabled: bool = True
    # 创作产出的平台限流词/违禁词规避（提示词规避 + 命中强制重写）。
    creation_compliance_enabled: bool = True
    # Skill 优化训练护栏：单次大模型调用超时(秒) + 整个训练的总时长上限(分钟,超时即中止判失败)。
    skill_opt_llm_timeout_seconds: int = 120
    skill_opt_max_minutes: int = 25
    # 僵死任务看门狗：running/cancel_requested 任务若超过这么多分钟没有新进展事件
    # （多半是 worker 进程被 OOM/强杀），自动标记为失败并告知前端。设大于最长合理静默期。
    task_stale_minutes: int = 20
    # 效果看板：省时估算常量（后台可调）+ 爆款判定倍数。
    dashboard_minutes_write_per_post: int = 40   # 手写一篇估时（分钟）
    dashboard_minutes_ai_draft_per_post: int = 8  # 用 AI 起草一篇估时（分钟）
    dashboard_minutes_research_per_distill: int = 30  # 一次蒸馏省下的研究对标估时（分钟）
    dashboard_viral_multiplier: float = 2.0  # 互动高于自身均值多少倍算「爆款」
    # 账号体检/对标的合成循环参数（偏诊断，阈值略低）。
    audit_max_revise_iterations: int = 1
    audit_min_quality_score: int = 75
    audit_llm_critic_enabled: bool = True
    tikhub_base_url: str = "https://api.tikhub.io"
    tikhub_api_key: str = ""
    tikhub_request_price_usd: float = 0.001
    tikhub_min_request_price_usd: float = 0.001
    tikhub_max_request_price_usd: float = 0.01
    # Minimum seconds between TikHub requests to proactively avoid 429s.
    # 0 disables throttling (default); ~0.15 paces to roughly the base 10 RPS plan.
    tikhub_min_request_interval_seconds: float = 0.0
    asr_enabled: bool = False
    asr_provider: str = "tencent_rec_task"
    asr_max_duration_seconds: int = 1800
    asr_poll_interval_seconds: int = 10
    # 识别结果轮询上限:超过则放弃该条并降级(从 30 分钟降到 5 分钟,真卡住的快速降级,不傻等)。
    asr_timeout_seconds: int = 300
    # 单条视频下载的硬上限:总墙钟时长 + 文件体积。超限抛错降级(防个别视频/慢节点拖死整批采集)。
    asr_download_max_seconds: int = 120
    asr_download_max_mb: int = 80
    tencent_asr_secret_id: str = ""
    tencent_asr_secret_key: str = ""
    tencent_asr_region: str = "ap-shanghai"
    tencent_asr_engine_model_type: str = "16k_zh"
    tencent_asr_res_text_format: int = 0
    tencent_cos_secret_id: str = ""
    tencent_cos_secret_key: str = ""
    tencent_cos_region: str = "ap-guangzhou"
    tencent_cos_bucket: str = ""
    tencent_cos_prefix: str = "pubsync/asr"
    public_api_base_url: str = ""
    static_dir: str = "static"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
