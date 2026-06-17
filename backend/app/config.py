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
    # 高赞优先的候选池深度 = clamp(采样数 × 倍数, 下限, 上限);系统决定,用户端不暴露。
    candidate_pool_oversample: int = 5
    candidate_pool_floor: int = 100
    candidate_pool_cap: int = 300
    # 合成循环（蒸馏）：质量不达标时自我修订的最大次数、达标阈值、是否启用推理型评审。
    synthesis_max_revise_iterations: int = 1
    synthesis_min_quality_score: int = 80
    synthesis_llm_critic_enabled: bool = True
    # AI 创作的合成循环参数（与蒸馏独立调参）。
    creation_max_revise_iterations: int = 1
    creation_min_quality_score: int = 80
    creation_llm_critic_enabled: bool = True
    # 创作产出的平台限流词/违禁词规避（提示词规避 + 命中强制重写）。
    creation_compliance_enabled: bool = True
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
    asr_timeout_seconds: int = 1800
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
