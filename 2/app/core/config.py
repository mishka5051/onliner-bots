from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "event-search"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    database_url: str = "postgresql+asyncpg://events:events@localhost:5432/event_search"
    search_provider: Literal["fake", "serpapi", "searxng"] = "fake"
    serpapi_api_key: str = ""
    searxng_base_url: str = "http://localhost:8080"
    search_results_limit: int = 10
    scoring_rules_path: Path = Path("config/scoring_rules.yaml")
    enrichment_enabled: bool = True
    supplementary_search_enabled: bool = True
    scheduler_enabled: bool = False
    scheduler_cron: str = "0 9 * * 1"
    shortlist_min_score: int = 50
    llm_provider: Literal["none", "openai"] = "none"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    return Settings()
