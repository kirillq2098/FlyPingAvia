"""WA-03: проверка Telegram Mini App initData (официальный HMAC)."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import parse_qsl, quote

logger = logging.getLogger(__name__)

MAX_INIT_DATA_LENGTH = 8192
MAX_INIT_DATA_PARAMS = 50
FUTURE_AUTH_SKEW_SECONDS = 30
DEFAULT_MAX_AGE_SECONDS = 3600


class TelegramAuthError(Exception):
    """Безопасная ошибка авторизации Mini App (без утечки secrets)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

    def as_detail(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


@dataclass(frozen=True)
class TelegramWebAppUser:
    id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    is_premium: bool | None = None
    auth_date: int | None = None

    @property
    def user_id(self) -> int:
        """Совместимость со старым dict-контрактом API."""
        return self.id


def _utc_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def validate_telegram_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    now: datetime | None = None,
) -> TelegramWebAppUser:
    """Официальная проверка Telegram WebApp initData.

    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data or not str(init_data).strip():
        raise TelegramAuthError(
            "MISSING_INIT_DATA",
            "Не удалось получить данные Telegram. Закройте и снова откройте приложение.",
        )

    raw = str(init_data)
    if len(raw) > MAX_INIT_DATA_LENGTH:
        raise TelegramAuthError(
            "INVALID_INIT_DATA",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )

    if not bot_token or bot_token == "REPLACE_ME":
        raise TelegramAuthError(
            "INVALID_INIT_DATA",
            "Авторизация временно недоступна. Попробуйте позже.",
        )

    pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=False)
    if len(pairs) > MAX_INIT_DATA_PARAMS:
        raise TelegramAuthError(
            "INVALID_INIT_DATA",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )

    for key, _value in pairs:
        if key == "":
            raise TelegramAuthError(
                "INVALID_INIT_DATA",
                "Некорректные данные Telegram. Закройте и снова откройте приложение.",
            )

    hash_values = [v for k, v in pairs if k == "hash"]
    if len(hash_values) == 0:
        raise TelegramAuthError(
            "INVALID_HASH",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )
    if len(hash_values) > 1:
        raise TelegramAuthError(
            "INVALID_HASH",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )
    received_hash = hash_values[0]
    if not received_hash:
        raise TelegramAuthError(
            "INVALID_HASH",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )

    check_pairs = [(k, v) for k, v in pairs if k != "hash"]
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(check_pairs, key=lambda x: x[0]))
    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    expected_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        logger.info("Telegram Mini App auth rejected: INVALID_HASH")
        raise TelegramAuthError(
            "INVALID_HASH",
            "Некорректные данные Telegram. Закройте и снова откройте приложение.",
        )

    parsed = {k: v for k, v in check_pairs}

    auth_raw = parsed.get("auth_date")
    if auth_raw is None or auth_raw == "":
        raise TelegramAuthError(
            "EXPIRED_INIT_DATA",
            "Сессия Telegram устарела. Закройте и снова откройте приложение.",
        )
    try:
        auth_date = int(auth_raw)
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError(
            "EXPIRED_INIT_DATA",
            "Сессия Telegram устарела. Закройте и снова откройте приложение.",
        ) from exc

    now_utc = _utc_now(now)
    now_ts = int(now_utc.timestamp())
    if auth_date > now_ts + FUTURE_AUTH_SKEW_SECONDS:
        logger.info("Telegram Mini App auth rejected: FUTURE_AUTH_DATE")
        raise TelegramAuthError(
            "FUTURE_AUTH_DATE",
            "Сессия Telegram недействительна. Закройте и снова откройте приложение.",
        )
    if max_age_seconds > 0 and (now_ts - auth_date) > max_age_seconds:
        logger.info("Telegram Mini App auth rejected: EXPIRED_INIT_DATA")
        raise TelegramAuthError(
            "EXPIRED_INIT_DATA",
            "Сессия Telegram устарела. Закройте и снова откройте приложение.",
        )

    user_raw = parsed.get("user")
    if user_raw is None or user_raw == "":
        raise TelegramAuthError(
            "INVALID_TELEGRAM_USER",
            "Не удалось определить пользователя Telegram.",
        )
    try:
        user_obj: Any = json.loads(user_raw)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise TelegramAuthError(
            "INVALID_TELEGRAM_USER",
            "Не удалось определить пользователя Telegram.",
        ) from exc
    if not isinstance(user_obj, dict) or not user_obj:
        raise TelegramAuthError(
            "INVALID_TELEGRAM_USER",
            "Не удалось определить пользователя Telegram.",
        )

    raw_id = user_obj.get("id")
    if isinstance(raw_id, bool) or not isinstance(raw_id, int):
        # JSON numbers that aren't int (or string ids) are invalid
        if isinstance(raw_id, str) and raw_id.isdigit():
            raise TelegramAuthError(
                "INVALID_TELEGRAM_USER",
                "Не удалось определить пользователя Telegram.",
            )
        raise TelegramAuthError(
            "INVALID_TELEGRAM_USER",
            "Не удалось определить пользователя Telegram.",
        )
    if raw_id <= 0:
        raise TelegramAuthError(
            "INVALID_TELEGRAM_USER",
            "Не удалось определить пользователя Telegram.",
        )

    premium = user_obj.get("is_premium")
    if premium is not None and not isinstance(premium, bool):
        premium = None

    return TelegramWebAppUser(
        id=int(raw_id),
        first_name=user_obj.get("first_name") if isinstance(user_obj.get("first_name"), str) else None,
        last_name=user_obj.get("last_name") if isinstance(user_obj.get("last_name"), str) else None,
        username=user_obj.get("username") if isinstance(user_obj.get("username"), str) else None,
        language_code=(
            user_obj.get("language_code")
            if isinstance(user_obj.get("language_code"), str)
            else None
        ),
        is_premium=premium,
        auth_date=auth_date,
    )


# Backward-compatible alias used by older imports/tests.
def validate_webapp_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    user = validate_telegram_init_data(
        init_data,
        bot_token=bot_token,
        max_age_seconds=max_age_seconds,
        now=now,
    )
    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "username": user.username,
            "language_code": user.language_code,
            "is_premium": user.is_premium,
        },
        "user_id": user.id,
        "username": user.username,
        "auth_date": user.auth_date,
        "telegram_user": user,
    }


def build_test_init_data(
    bot_token: str,
    user_id: int,
    username: str | None = "dev",
    *,
    first_name: str = "Dev",
    last_name: str | None = None,
    auth_date: int | None = None,
    extra: Optional[dict[str, str]] = None,
    include_query_id: bool = True,
) -> str:
    """Собрать валидный initData для unit-тестов (без URL-encoding значений как Telegram)."""
    if auth_date is None:
        auth_date = int(datetime.now(timezone.utc).timestamp())
    user_obj: dict[str, Any] = {
        "id": user_id,
        "first_name": first_name,
    }
    if username is not None:
        user_obj["username"] = username
    if last_name is not None:
        user_obj["last_name"] = last_name
    user = json.dumps(
        user_obj,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    payload: dict[str, str] = {
        "auth_date": str(auth_date),
        "user": user,
    }
    if include_query_id:
        payload["query_id"] = "AAEAAATEST"
    if extra:
        payload.update({str(k): str(v) for k, v in extra.items()})

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    payload["hash"] = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    # Telegram sends application/x-www-form-urlencoded; quote values safely.
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in payload.items())
