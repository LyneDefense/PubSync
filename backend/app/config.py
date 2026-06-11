from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pubsync:pubsync@localhost:5432/pubsync"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    admin_username: str = "admin"
    admin_password: str = "change_me"
    auth_secret: str = ""
    session_hours: int = 24
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
    tikhub_base_url: str = "https://api.tikhub.io"
    tikhub_api_key: str = ""
    tikhub_request_price_usd: float = 0.001
    tikhub_min_request_price_usd: float = 0.001
    tikhub_max_request_price_usd: float = 0.01
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
