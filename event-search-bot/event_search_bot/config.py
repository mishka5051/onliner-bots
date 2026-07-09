from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    searxng_base_url: str = "http://localhost:8080"
    query_suffix: str = ""
    log_level: str = "INFO"
    search_timeout: float = 60.0

    search_results_limit: int = 10
    search_pages_max: int = 2

    deep_search_results_limit: int = 80
    deep_search_pages_max: int = 4
    deep_enrichment_max_events: int = 400
    deep_enrichment_max_rounds: int = 8
    deep_enrichment_batch_size: int = 30
    deep_catalog_expansion_max: int = 150
    deep_catalog_max_links: int = 18
    page_fetch_timeout: float = 15.0
    page_fetch_concurrency: int = 8
    deep_search_max_active_per_user: int = 3

    bot_data_dir: str = "data"

    # Общая БД заявок с partnership-bot (Docker volume, без веб-сервиса)
    partnership_data_dir: str = "partnership-data"
    allowed_telegram_ids: str = ""
    leads_poll_interval_sec: float = 90.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
