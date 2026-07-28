from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Optional
from urllib.parse import parse_qsl


def validate_webapp_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict[str, Any]:
    """
    Проверка подписи Telegram WebApp initData.
    https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise ValueError("Пустой initData")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise ValueError("Нет hash в initData")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash):
        raise ValueError("Неверная подпись initData")

    auth_date = int(parsed.get("auth_date", "0") or 0)
    if auth_date and max_age_seconds > 0:
        if time.time() - auth_date > max_age_seconds:
            raise ValueError("initData устарел")

    user_raw = parsed.get("user")
    user = json.loads(user_raw) if user_raw else {}
    return {
        "user": user,
        "user_id": int(user.get("id") or 0),
        "username": user.get("username"),
        "auth_date": auth_date,
        "raw": parsed,
    }


def build_test_init_data(bot_token: str, user_id: int, username: str = "dev") -> str:
    """Собрать валидный initData для unit-тестов."""
    user = json.dumps({"id": user_id, "username": username, "first_name": "Dev"}, separators=(",", ":"))
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAEAAATEST",
        "user": user,
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    payload["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return "&".join(f"{k}={v}" for k, v in payload.items())
