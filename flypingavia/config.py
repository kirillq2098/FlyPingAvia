from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфиг. Принимает и наши имена, и ваши из .env (TELEGRAM_TOKEN и т.д.)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(
        default="REPLACE_ME",
        validation_alias=AliasChoices("BOT_TOKEN", "TELEGRAM_TOKEN", "bot_token"),
    )
    travelpayouts_token: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TRAVELPAYOUTS_TOKEN",
            "AVIASALES_API_TOKEN",
            "travelpayouts_token",
        ),
    )
    affiliate_marker: str = Field(
        default="flypingavia",
        validation_alias=AliasChoices("AFFILIATE_MARKER", "affiliate_marker"),
    )
    # Числовой partner ID из кабинета Travelpayouts (для Flight Search API).
    # Если пусто — берётся AFFILIATE_MARKER.
    travelpayouts_search_marker: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TRAVELPAYOUTS_SEARCH_MARKER",
            "TRAVELPAYOUTS_MARKER",
            "travelpayouts_search_marker",
        ),
    )
    # off | multi | always — когда звать живой поиск за состав пассажиров
    live_search_mode: str = Field(
        default="multi",
        validation_alias=AliasChoices("LIVE_SEARCH_MODE", "live_search_mode"),
    )
    live_search_host: str = Field(
        default="flypingavia.app",
        validation_alias=AliasChoices("LIVE_SEARCH_HOST", "live_search_host"),
    )
    free_watch_limit: int = Field(
        default=0,
        validation_alias=AliasChoices("FREE_WATCH_LIMIT", "free_watch_limit"),
        description="0 = без лимита",
    )
    check_interval_minutes: int = Field(
        default=30,
        validation_alias=AliasChoices("CHECK_INTERVAL_MINUTES", "check_interval_minutes"),
    )
    check_interval_seconds: int | None = Field(
        default=None,
        validation_alias=AliasChoices("CHECK_INTERVAL_SECONDS", "check_interval_seconds"),
    )
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/flypingavia.db",
        validation_alias=AliasChoices("DATABASE_URL", "database_url"),
    )
    db_path: str | None = Field(
        default=None,
        validation_alias=AliasChoices("DB_PATH", "db_path"),
    )
    currency: str = Field(
        default="rub",
        validation_alias=AliasChoices("CURRENCY", "currency"),
    )
    webapp_url: str = Field(
        default="",
        validation_alias=AliasChoices("WEBAPP_URL", "webapp_url"),
        description="Публичный HTTPS URL Mini App, например https://xxx.ngrok.io",
    )
    webapp_host: str = Field(
        default="0.0.0.0",
        validation_alias=AliasChoices("WEBAPP_HOST", "webapp_host"),
    )
    webapp_port: int = Field(
        default=8080,
        validation_alias=AliasChoices("WEBAPP_PORT", "webapp_port"),
    )
    # Только для локальной отладки Mini App в браузере без Telegram
    webapp_dev_user_id: int = Field(
        default=0,
        validation_alias=AliasChoices("WEBAPP_DEV_USER_ID", "webapp_dev_user_id"),
    )

    @model_validator(mode="after")
    def _apply_db_path(self) -> Settings:
        if self.db_path:
            path = Path(self.db_path)
            self.database_url = f"sqlite+aiosqlite:///{path.as_posix()}"
        return self

    @property
    def is_demo_prices(self) -> bool:
        return not bool(self.travelpayouts_token.strip())

    @property
    def search_marker(self) -> str:
        return (self.travelpayouts_search_marker or self.affiliate_marker or "").strip()

    @property
    def live_search_enabled(self) -> bool:
        mode = (self.live_search_mode or "off").strip().lower()
        return mode in {"multi", "always", "on", "1", "true"} and bool(
            self.travelpayouts_token.strip() and self.search_marker
        )

    @property
    def poll_interval_seconds(self) -> int:
        if self.check_interval_seconds is not None and self.check_interval_seconds > 0:
            return self.check_interval_seconds
        return max(int(self.check_interval_minutes) * 60, 30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
