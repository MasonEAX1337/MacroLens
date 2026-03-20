from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MacroLens API"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/macrolens"
    fred_api_key: str = ""
    explanation_provider: str = "rules_based"
    explanation_fallback_provider: str = "rules_based"
    explanation_allow_fallback: bool = True
    explanation_model: str = "macro-template-v1"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-5-mini"
    openai_timeout_seconds: float = 30.0
    openai_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_model: str = "gemini-3.1-flash-lite-preview"
    gemini_timeout_seconds: float = 30.0
    gemini_api_key: str = ""
    news_context_provider: str = "gdelt"
    news_context_window_days: int = 7
    news_context_max_articles: int = 5
    news_context_language: str = "English"
    anomaly_cluster_window_days: int = 7
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2/doc"
    gdelt_min_interval_seconds: float = 8.0
    gdelt_retry_attempts: int = 4
    gdelt_retry_backoff_seconds: float = 8.0
    gdelt_max_anomaly_age_days: int = 3650
    anthropic_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def get_cors_origins() -> list[str]:
    return [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]
