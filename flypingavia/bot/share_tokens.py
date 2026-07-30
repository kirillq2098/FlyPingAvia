"""TG-04: opaque share tokens для deep-link копирования Watch."""

from __future__ import annotations

import hashlib
import secrets

from flypingavia.bot.start_payload import normalize_start_payload

SHARE_PREFIX = "share_"
# 22 bytes ≈ 176 бит энтропии; base64url ≈ 30 символов; share_ + token ≤ 64.
_TOKEN_BYTES = 22

INVALID_SHARE_MESSAGE = (
    "Эта ссылка больше не действует.\n\n"
    "Попросите отправителя создать новую ссылку."
)

OWN_SHARE_MESSAGE = "Это ваша подписка — копия не требуется."

MAX_ACTIVE_SHARES_PER_WATCH = 10


def generate_share_token() -> str:
    """Сырой opaque token (без prefix), cryptographic entropy ≥ 128 bit."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_share_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def build_share_payload(raw_token: str) -> str:
    payload = f"{SHARE_PREFIX}{raw_token}"
    normalized = normalize_start_payload(payload)
    if normalized is None:
        raise ValueError("Share payload не проходит whitelist Telegram start")
    return normalized


def parse_share_payload(payload: str | None) -> str | None:
    """Вернуть raw token без share_, если формат корректен."""
    normalized = normalize_start_payload(payload)
    if not normalized or not normalized.startswith(SHARE_PREFIX):
        return None
    raw = normalized[len(SHARE_PREFIX) :]
    if not raw:
        return None
    # raw сам должен быть безопасным подмножеством whitelist
    if normalize_start_payload(raw) is None:
        return None
    return raw
