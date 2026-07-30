"""TG-03: deep-link start payload и Telegram start URL."""

from __future__ import annotations

import re
from urllib.parse import urlencode

START_PAYLOAD_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Telegram usernames: 5–32 chars, start with letter (как в config TELEGRAM_BOT_USERNAME).
BOT_USERNAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{4,31}$")


def normalize_start_payload(value: str | None) -> str | None:
    """Whitelist Telegram start payload. Невалидное → None (без исключений)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if not START_PAYLOAD_PATTERN.fullmatch(text):
        return None
    return text


def build_telegram_start_link(
    *,
    bot_username: str,
    payload: str | None = None,
) -> str:
    """Собрать https://t.me/<username>?start=<payload> без token и без сети."""
    username = (bot_username or "").strip().lstrip("@")
    if not BOT_USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Некорректный bot username "
            "(5–32 символа, латиница/цифры/_, начинается с буквы)"
        )
    base = f"https://t.me/{username}"
    normalized = normalize_start_payload(payload)
    if normalized is None:
        if payload is not None and str(payload).strip() != "":
            raise ValueError("Некорректный start payload")
        return base
    return f"{base}?{urlencode({'start': normalized})}"
