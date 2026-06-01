from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://pubsync:pubsync@localhost:5432/pubsync"
    cors_origins: str = "http://localhost:5173,http://localhost:8000"
    admin_username: str = "admin"
    admin_password: str = "change_me"
    auth_secret: str = ""
    session_hours: int = 24
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
    public_api_base_url: str = ""
    static_dir: str = "static"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
