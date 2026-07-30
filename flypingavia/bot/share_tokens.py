"""TG-04: opaque share tokens и HMAC callback proof для deep-link копирования Watch."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from flypingavia.bot.start_payload import normalize_start_payload

SHARE_PREFIX = "share_"
# 22 bytes ≈ 176 бит энтропии; base64url ≈ 30 символов; share_ + token ≤ 64.
_TOKEN_BYTES = 22

# Attribution: raw share token никогда не пишется в users.*_start_source.
ATTRIBUTION_SHARE_SOURCE = "share"

# Telegram callback_data ≤ 64 bytes: sc:<share_id>:<exp>:<sig>
CALLBACK_PROOF_PREFIX = "sc"
_SIG_BYTES = 15  # 15 → base64url без padding ≈ 20 символов
TELEGRAM_CALLBACK_DATA_MAX = 64

INVALID_SHARE_MESSAGE = (
    "Эта ссылка больше не действует.\n\n"
    "Попросите отправителя создать новую ссылку."
)

OWN_SHARE_MESSAGE = "Это ваша подписка — копия не требуется."

MAX_ACTIVE_SHARES_PER_WATCH = 10

# Стабильный default только для development/test (не для production).
DEV_SHARE_CALLBACK_SECRET = "dev-watch-share-callback-secret-do-not-use-prod"


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


def attribution_source_for_start_payload(payload: str | None) -> str | None:
    """TG-03 source для записи в БД: share_* → «share», иначе payload как есть.

    Raw share token не сохраняется. None → None.
    """
    if payload is None:
        return None
    normalized = normalize_start_payload(payload)
    if normalized is None:
        return None
    if parse_share_payload(normalized) is not None:
        return ATTRIBUTION_SHARE_SOURCE
    return normalized


def _b64url_nopad(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def create_share_callback_proof(
    *,
    share_id: int,
    telegram_user_id: int,
    expires_at: datetime,
    secret: str,
) -> str:
    """Подписанный proof для confirm (≤64 bytes). Без raw token."""
    if not secret:
        raise ValueError("WATCH_SHARE_CALLBACK_SECRET пуст")
    exp = int(_aware_utc(expires_at).timestamp())
    msg = f"{int(share_id)}:{int(telegram_user_id)}:{exp}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    sig = _b64url_nopad(digest[:_SIG_BYTES])
    proof = f"{CALLBACK_PROOF_PREFIX}:{int(share_id)}:{exp}:{sig}"
    if len(proof.encode("utf-8")) > TELEGRAM_CALLBACK_DATA_MAX:
        raise ValueError("Share callback proof превышает лимит Telegram (64 bytes)")
    return proof


def verify_share_callback_proof(
    value: str,
    *,
    telegram_user_id: int,
    secret: str,
    now: datetime,
) -> int | None:
    """Проверить proof; вернуть share_id или None. Без раскрытия причины."""
    if not value or not secret:
        return None
    parts = value.split(":")
    if len(parts) != 4:
        return None
    prefix, share_s, exp_s, sig = parts
    if prefix != CALLBACK_PROOF_PREFIX:
        return None
    if not share_s.isdigit() or not exp_s.isdigit() or not sig:
        return None
    share_id = int(share_s)
    exp = int(exp_s)
    now_ts = int(_aware_utc(now).timestamp())
    if exp <= now_ts:
        return None
    msg = f"{share_id}:{int(telegram_user_id)}:{exp}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()
    expected = _b64url_nopad(digest[:_SIG_BYTES])
    if not hmac.compare_digest(expected, sig):
        return None
    return share_id
