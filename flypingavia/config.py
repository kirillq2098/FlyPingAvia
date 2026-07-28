from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str = "REPLACE_ME"
    travelpayouts_token: str = ""
    affiliate_marker: str = "flypingavia"
    free_watch_limit: int = 2
    check_interval_minutes: int = 30
    database_url: str = "sqlite+aiosqlite:///./data/flypingavia.db"

    @property
    def is_demo_prices(self) -> bool:
        return not bool(self.travelpayouts_token.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
