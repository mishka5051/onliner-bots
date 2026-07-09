from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str
    log_level: str = "INFO"
    bot_data_dir: str = "data"
    # Telegram ID сотрудников для уведомлений о новых заявках (через запятую)
    notify_telegram_ids: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


def staff_notify_ids() -> set[int]:
    raw = get_settings().notify_telegram_ids.strip()
    if not raw:
        return set()
    result: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part.isdigit():
            result.add(int(part))
    return result
