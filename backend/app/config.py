from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pubsync:pubsync@localhost:5432/pubsync"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    publish_time_hour: int = 8
    publish_time_minute: int = 0
    auto_send_wechat_draft: bool = False
    admin_username: str = "admin"
    admin_password: str = "change_me"
    auth_secret: str = ""
    session_hours: int = 24
    wechat_app_id: str = ""
    wechat_app_secret: str = ""
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
    generate_article_images: bool = True
    max_article_images: int = 3
    min_article_images: int = 1
    news_source_urls: str = ""
    international_news_source_urls: str = ""
    domestic_news_source_urls: str = ""
    news_per_source_limit: int = 8
    international_news_candidates: int = 40
    domestic_news_candidates: int = 40
    news_lookback_hours: int = 72
    max_news_candidates: int = 80
    article_news_limit: int = 10
    article_news_lookback_hours: int = 72
    article_domestic_min: int = 1
    article_domestic_target: int = 3
    article_domestic_max: int = 4
    article_international_min: int = 3
    article_international_target: int = 6
    article_international_max: int = 7
    public_api_base_url: str = ""
    static_dir: str = "static"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
