from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from flypingavia.webapp_url import (
    ALLOWED_APP_ENVS,
    is_telegram_safe_webapp_url,
    is_temporary_tunnel_hostname,
    normalize_webapp_url,
)


class Settings(BaseSettings):
    """Конфиг. Принимает и наши имена, и ваши из .env (TELEGRAM_TOKEN и т.д.)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = Field(
        default="development",
        validation_alias=AliasChoices("APP_ENV", "app_env"),
        description="development | production | test",
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
        description="Canonical публичный URL Mini App (HTTPS в production)",
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
    # WA-03: срок жизни Telegram WebApp initData (секунды)
    telegram_init_data_max_age_seconds: int = Field(
        default=3600,
        gt=0,
        validation_alias=AliasChoices(
            "TELEGRAM_INIT_DATA_MAX_AGE_SECONDS",
            "telegram_init_data_max_age_seconds",
        ),
        description="Максимальный возраст initData (default 3600)",
    )
    # Публичный @username бота без @ (для кнопки «Открыть бота» вне Telegram)
    telegram_bot_username: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TELEGRAM_BOT_USERNAME",
            "telegram_bot_username",
        ),
        description="Публичный username бота без @ (опционально)",
    )
    # Uvicorn: кому доверять X-Forwarded-* (IP reverse proxy на loopback)
    forwarded_allow_ips: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("FORWARDED_ALLOW_IPS", "forwarded_allow_ips"),
        description="CSV IP для --forwarded-allow-ips (не используйте * на публичном bind)",
    )

    notification_cooldown_hours: float = Field(
        default=24.0,
        ge=0,
        validation_alias=AliasChoices(
            "NOTIFICATION_COOLDOWN_HOURS",
            "notification_cooldown_hours",
        ),
        description="Минимальный интервал между алертами по одному watch (часы)",
    )
    min_price_delta: float = Field(
        default=500.0,
        ge=0,
        validation_alias=AliasChoices("MIN_PRICE_DELTA", "min_price_delta"),
        description="Минимальное падение цены (в валюте watch) для алерта внутри cooldown",
    )
    # TG-04: срок жизни share-ссылки (часы)
    watch_share_ttl_hours: int = Field(
        default=168,
        ge=1,
        le=720,
        validation_alias=AliasChoices(
            "WATCH_SHARE_TTL_HOURS",
            "watch_share_ttl_hours",
        ),
        description="TTL share deep-link в часах (default 168 = 7 дней)",
    )
    watch_share_max_uses: int = Field(
        default=20,
        ge=1,
        le=1000,
        validation_alias=AliasChoices(
            "WATCH_SHARE_MAX_USES",
            "watch_share_max_uses",
        ),
        description="Максимум успешных копий по одной share-ссылке",
    )
    watch_share_callback_secret: str = Field(
        default="",
        validation_alias=AliasChoices(
            "WATCH_SHARE_CALLBACK_SECRET",
            "watch_share_callback_secret",
        ),
        description="HMAC secret для share confirm callback (не bot token)",
    )
    watch_share_callback_ttl_seconds: int = Field(
        default=900,
        ge=60,
        le=3600,
        validation_alias=AliasChoices(
            "WATCH_SHARE_CALLBACK_TTL_SECONDS",
            "watch_share_callback_ttl_seconds",
        ),
        description="TTL HMAC callback proof для share confirm (секунды)",
    )
    # RL-03: admin health alerts
    admin_telegram_chat_id: int | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "ADMIN_TELEGRAM_CHAT_ID",
            "admin_telegram_chat_id",
        ),
        description="Telegram chat/user id для служебных алертов (пусто = выкл)",
    )
    admin_alerts_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "ADMIN_ALERTS_ENABLED",
            "admin_alerts_enabled",
        ),
        description="Включить отправку admin health alerts (нужен chat id)",
    )
    admin_alert_failure_threshold: int = Field(
        default=3,
        ge=1,
        le=100,
        validation_alias=AliasChoices(
            "ADMIN_ALERT_FAILURE_THRESHOLD",
            "admin_alert_failure_threshold",
        ),
        description="Сколько подряд ошибок до первого admin alert",
    )
    admin_alert_cooldown_seconds: int = Field(
        default=3600,
        ge=60,
        le=86400,
        validation_alias=AliasChoices(
            "ADMIN_ALERT_COOLDOWN_SECONDS",
            "admin_alert_cooldown_seconds",
        ),
        description="Cooldownoldown повторных failure-алертов по одному инциденту",
    )
    health_monitor_interval_seconds: int = Field(
        default=60,
        ge=30,
        le=3600,
        validation_alias=AliasChoices(
            "HEALTH_MONITOR_INTERVAL_SECONDS",
            "health_monitor_interval_seconds",
        ),
        description="Интервал health monitor loop",
    )
    health_startup_grace_seconds: int = Field(
        default=300,
        ge=0,
        le=3600,
        validation_alias=AliasChoices(
            "HEALTH_STARTUP_GRACE_SECONDS",
            "health_startup_grace_seconds",
        ),
        description="Grace period без checker_stalled после старта",
    )
    checker_stale_after_seconds: int | None = Field(
        default=None,
        ge=60,
        le=86400,
        validation_alias=AliasChoices(
            "CHECKER_STALE_AFTER_SECONDS",
            "checker_stale_after_seconds",
        ),
        description="Возраст heartbeat для checker_stalled (default max(interval*3, 900))",
    )
    webapp_healthcheck_timeout_seconds: int = Field(
        default=5,
        ge=1,
        le=30,
        validation_alias=AliasChoices(
            "WEBAPP_HEALTHCHECK_TIMEOUT_SECONDS",
            "webapp_healthcheck_timeout_seconds",
        ),
        description="Timeout локальной проверки Mini App health",
    )
    admin_telegram_user_ids: str = Field(
        default="",
        validation_alias=AliasChoices(
            "ADMIN_TELEGRAM_USER_IDS",
            "admin_telegram_user_ids",
        ),
        description="CSV Telegram user id для /admin_health (если chat — группа)",
    )
    # Closed Beta Phase A
    beta_enabled: bool = Field(
        default=False,
        validation_alias=AliasChoices("BETA_ENABLED", "beta_enabled"),
        description="Включить регистрацию по ?start=beta_<code>",
    )
    beta_invite_codes: str = Field(
        default="",
        validation_alias=AliasChoices("BETA_INVITE_CODES", "beta_invite_codes"),
        description="CSV кодов волны без префикса beta_ (например w1)",
    )
    beta_survey_a_delay_seconds: int = Field(
        default=90,
        ge=30,
        le=600,
        validation_alias=AliasChoices(
            "BETA_SURVEY_A_DELAY_SECONDS",
            "beta_survey_a_delay_seconds",
        ),
        description="Задержка Survey A после первой подписки (секунды)",
    )
    beta_dispatcher_interval_seconds: int = Field(
        default=45,
        ge=15,
        le=120,
        validation_alias=AliasChoices(
            "BETA_DISPATCHER_INTERVAL_SECONDS",
            "beta_dispatcher_interval_seconds",
        ),
        description="Интервал beta_dispatcher (секунды)",
    )
    # TR-04: единая бизнес-таймзона для отображения last_checked_at (БД хранит UTC)
    display_timezone: str = Field(
        default="Europe/Moscow",
        validation_alias=AliasChoices("DISPLAY_TIMEZONE", "display_timezone"),
        description="IANA timezone для показа времени проверки (default Europe/Moscow)",
    )

    @field_validator("admin_telegram_chat_id", mode="before")
    @classmethod
    def _parse_admin_chat_id(cls, value):
        if value is None:
            return None
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _normalize_and_validate(self) -> Settings:
        env = (self.app_env or "").strip().lower()
        if env not in ALLOWED_APP_ENVS:
            raise ValueError(
                f"Некорректный APP_ENV={self.app_env!r}. "
                f"Допустимо: {', '.join(sorted(ALLOWED_APP_ENVS))}"
            )
        self.app_env = env

        if self.db_path:
            path = Path(self.db_path)
            self.database_url = f"sqlite+aiosqlite:///{path.as_posix()}"

        name = (self.display_timezone or "").strip()
        if not name:
            raise ValueError(
                "DISPLAY_TIMEZONE пуст. Укажите IANA timezone, например Europe/Moscow"
            )
        try:
            ZoneInfo(name)
        except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
            raise ValueError(
                f"Некорректный DISPLAY_TIMEZONE={name!r}. "
                "Ожидается IANA имя, например Europe/Moscow"
            ) from exc
        self.display_timezone = name

        try:
            self.webapp_url = normalize_webapp_url(self.webapp_url, app_env=self.app_env)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

        if self.app_env == "production" and int(self.webapp_dev_user_id or 0) != 0:
            raise ValueError(
                "В production WEBAPP_DEV_USER_ID должен быть 0 "
                "(отладка без Telegram запрещена)"
            )

        username = (self.telegram_bot_username or "").strip().lstrip("@")
        if username:
            import re

            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{4,31}", username):
                raise ValueError(
                    "TELEGRAM_BOT_USERNAME: некорректный username "
                    "(5–32 символа, латиница/цифры/_, начинается с буквы)"
                )
        self.telegram_bot_username = username

        secret = (self.watch_share_callback_secret or "").strip()
        if self.app_env == "production":
            if len(secret) < 32:
                raise ValueError(
                    "В production WATCH_SHARE_CALLBACK_SECRET обязателен "
                    "(минимум 32 символа). Не используйте BOT_TOKEN."
                )
            self.watch_share_callback_secret = secret
        else:
            # development/test: стабильный default, чтобы кнопки переживали рестарт
            from flypingavia.bot.share_tokens import DEV_SHARE_CALLBACK_SECRET

            self.watch_share_callback_secret = secret or DEV_SHARE_CALLBACK_SECRET

        return self

    @property
    def admin_alerts_active(self) -> bool:
        return bool(self.admin_alerts_enabled and self.admin_telegram_chat_id is not None)

    @property
    def effective_checker_stale_after_seconds(self) -> int:
        if self.checker_stale_after_seconds is not None and self.checker_stale_after_seconds > 0:
            return int(self.checker_stale_after_seconds)
        return max(int(self.poll_interval_seconds) * 3, 900)

    @property
    def admin_user_id_set(self) -> set[int]:
        out: set[int] = set()
        raw = (self.admin_telegram_user_ids or "").strip()
        if raw:
            for part in raw.split(","):
                part = part.strip()
                if not part:
                    continue
                try:
                    out.add(int(part))
                except ValueError:
                    continue
        if self.admin_telegram_chat_id is not None and self.admin_telegram_chat_id > 0:
            out.add(int(self.admin_telegram_chat_id))
        return out

    @property
    def beta_invite_code_set(self) -> set[str]:
        out: set[str] = set()
        raw = (self.beta_invite_codes or "").strip()
        if not raw:
            return out
        for part in raw.split(","):
            code = part.strip().lower()
            if code.startswith("beta_"):
                code = code[5:]
            if code:
                out.add(code)
        return out

    @property
    def display_tz(self) -> ZoneInfo:
        return ZoneInfo(self.display_timezone)

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_test(self) -> bool:
        return self.app_env == "test"

    @property
    def webapp_origin(self) -> str | None:
        return self.webapp_url or None

    @property
    def webapp_https(self) -> bool:
        return bool(self.webapp_url) and self.webapp_url.startswith("https://")

    @property
    def webapp_configured(self) -> bool:
        return bool(self.webapp_url)

    @property
    def telegram_webapp_url(self) -> str | None:
        """URL для Telegram Web App кнопок (только публичный HTTPS)."""
        if is_telegram_safe_webapp_url(self.webapp_url):
            return self.webapp_url
        return None

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

    def readiness_issues(self) -> list[str]:
        """Коды проблем относительно текущего APP_ENV (без secrets)."""
        from urllib.parse import urlparse

        issues: list[str] = []
        if self.app_env in {"development", "test"}:
            # Локально/в тестах процесс считается готовым без публичного HTTPS.
            return issues

        # production
        if not self.webapp_url:
            issues.append("WEBAPP_URL_NOT_CONFIGURED")
        elif not self.webapp_https:
            issues.append("WEBAPP_URL_NOT_HTTPS")
        else:
            # Defense-in-depth: штатная валидация уже отклоняет temporary URL.
            host = urlparse(self.webapp_url).hostname
            if is_temporary_tunnel_hostname(host):
                issues.append("TEMPORARY_WEBAPP_URL")
        if int(self.webapp_dev_user_id or 0) != 0:
            issues.append("WEBAPP_DEV_USER_ENABLED")
        if self.is_demo_prices:
            issues.append("DEMO_PRICES_ENABLED")
        if not self.bot_token or self.bot_token == "REPLACE_ME":
            issues.append("BOT_TOKEN_MISSING")
        return issues

    @property
    def is_ready(self) -> bool:
        return not self.readiness_issues()


@lru_cache
def get_settings() -> Settings:
    return Settings()
