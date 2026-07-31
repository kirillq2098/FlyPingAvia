"""Safe Mini App session diagnostics (BUG-02.5) — no secrets / initData / tokens."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_DEFAULT_PATH = "/app/logs/miniapp-diagnostic.log"
_lock = threading.Lock()

# Keys that must never appear in diagnostic payloads (values or nested).
_FORBIDDEN_KEY_RE = re.compile(
    r"(auth(orization)?|init[_-]?data|bot[_-]?token|cookie|password|secret|"
    r"query_id|signature|start_param|tgwebappdata|telegram[_-]?id|"
    r"user[_-]?id|chat[_-]?id|phone|hash)$",
    re.I,
)

_ALLOWED_TOP = frozenset(
    {
        "ts",
        "kind",
        "session_id",
        "event",
        "stage",
        "boot_state",
        "elapsed_ms",
        "asset",
        "launch_mode",
        "classification",
        "path",
        "origin",
        "status",
        "http_status",
        "duration_ms",
        "endpoint",
        "error_code",
        "request_id",
        "client_ip_masked",
        "ua_sanitized",
        "has_init_data",
        "init_data_len",
        "has_cached_init",
        "inside_telegram",
        "ui_started",
        "has_telegram",
        "has_webapp",
        "platform",
        "sdk_fallback",
        "sdk_source",
        "unsafe_keys",
        "unsafe_has_user",
        "hash_present",
        "hash_len",
        "hash_params",
        "hash_param_lens",
        "search_present",
        "search_len",
        "search_params",
        "search_param_lens",
        "has_tgwebappdata",
        "tgwebappdata_len",
        "has_tgwebappversion",
        "has_tgwebappplatform",
        "has_tgwebapptheme",
        "decode_ok",
        "decode_passes",
        "extract_ok",
        "extract_source",
        "extract_len",
        "spa_path",
        "sdk_init_len",
        "storage_present",
        "href_len",
        "referrer_origin",
        "referrer_path",
        "has_webview_proxy",
        "nav_type",
        "visibility",
        "ready_state",
        "online",
        "url_changed",
        "ready_called",
        "expand_called",
        "webapp_version",
        "color_scheme",
        "is_expanded",
        "viewport_height",
        "viewport_stable_height",
        "has_telegram_webview",
        "ua",
        "nav_platform",
        "nav_vendor",
        "language",
        "languages",
        "ua_data_present",
        "ua_brands",
        "ua_platform",
        "screen_w",
        "screen_h",
        "dpr",
        "timezone",
        "cookie_enabled",
        "local_storage_ok",
        "session_storage_ok",
        "bot_username",
        "bot_id",
        "button_type",
        "button_url",
        "message_id",
        "chat_id_masked",
        "polling",
        "menu_button_type",
        "menu_button_url",
        "detail",
    }
)


def diag_log_path() -> Path:
    return Path(os.environ.get("MINIAPP_DIAG_LOG_PATH", _DEFAULT_PATH))


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def mask_ip(ip: str | None) -> str:
    if not ip:
        return "-"
    ip = str(ip).strip()
    if ":" in ip:  # IPv6 — keep first 2 hextets
        parts = ip.split(":")
        return ":".join(parts[:2] + ["…"]) if len(parts) > 2 else ip
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.{parts[2]}…"
    return ip[:8] + "…"


def mask_chat_id(chat_id: int | str | None) -> str:
    if chat_id is None:
        return "-"
    raw = str(chat_id)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"chat_{digest}"


def sanitize_ua(ua: str | None, max_len: int = 240) -> str:
    if not ua:
        return ""
    # Strip obvious tokens / long hex
    cleaned = re.sub(r"(?i)(authorization|bearer|tma)\s+\S+", "[redacted]", ua)
    cleaned = re.sub(r"[0-9a-f]{32,}", "[hex]", cleaned, flags=re.I)
    return cleaned[:max_len]


def _scrub_value(key: str, value: Any) -> Any:
    if _FORBIDDEN_KEY_RE.search(str(key)):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(k)[:64]: _scrub_value(str(k), v) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        return [_scrub_value(key, v) for v in value[:40]]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if abs(value) > 10**12:
            return 0
        return value
    if value is None:
        return None
    s = str(value)
    # Never keep initData-like payloads
    if "hash=" in s and ("auth_date=" in s or "user=" in s):
        return f"[redacted_len_{min(len(s), 100000)}]"
    if "tgWebAppData=" in s or "query_id=" in s:
        return f"[redacted_len_{min(len(s), 100000)}]"
    return s[:500]


def sanitize_record(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        k = str(key)[:64]
        if k not in _ALLOWED_TOP and not k.startswith("x_"):
            continue
        if _FORBIDDEN_KEY_RE.search(k):
            continue
        out[k] = _scrub_value(k, value)
    return out


def classify_session_events(events: list[dict[str, Any]]) -> str:
    """Return A–H classification from a list of sanitized events."""
    if not events:
        return "F"
    assets = {e.get("asset") for e in events if e.get("asset")}
    if assets and not any(str(a).endswith("bug023") or "bug025" in str(a) or "bug02" in str(a) for a in assets):
        # old unknown asset
        if any("bug02" not in str(a) and "0.3.0" in str(a) for a in assets):
            return "G"
    stages = [str(e.get("event") or e.get("stage") or "") for e in events]
    has_me_start = any(s in ("api_me_start", "api_me") for s in stages)
    has_me_ok = any(s in ("api_me_ok", "api_me_response", "bootstrap_success") for s in stages)
    has_me_fail = any(s in ("api_me_error", "api_me_fail") for s in stages)
    statuses = [int(e.get("http_status") or e.get("status") or 0) for e in events]
    tgdata = any(bool(e.get("has_tgwebappdata")) or int(e.get("tgwebappdata_len") or 0) > 0 for e in events)
    extract_ok = any(bool(e.get("extract_ok")) for e in events)
    has_init = any(bool(e.get("has_init_data")) or int(e.get("init_data_len") or 0) > 0 for e in events)
    missing = any(s == "missing_init_data" for s in stages)
    ui_err = any(s in ("ui_error", "unhandled_error", "unhandled_rejection") for s in stages)

    if any(int(s) in (401, 403) for s in statuses) and has_me_start:
        return "D"
    if has_me_ok and any(s == 200 for s in statuses):
        if ui_err:
            return "E"
        return "E" if ui_err else "ok_pending_soak"  # success path — not A–H failure
    if has_me_ok:
        return "E" if ui_err else "ok_pending_soak"
    if has_init or extract_ok:
        if not has_me_start:
            return "C"
        if has_me_fail:
            return "D"
    if tgdata and not extract_ok and not has_init:
        return "B"
    if missing or (not tgdata and not has_init):
        origins = {str(e.get("origin") or "") for e in events if e.get("origin")}
        if origins and not any("app.flyping.ru" in o for o in origins):
            return "H"
        return "A"
    if not any(e.get("kind") == "frontend" or e.get("event") for e in events):
        return "F"
    return "A"


CLASSIFICATION_LABELS = {
    "A": "Telegram не передал tgWebAppData",
    "B": "tgWebAppData был в URL, parser не извлёк",
    "C": "parser извлёк, /api/me не вызван",
    "D": "/api/me вызван и получил 401/403",
    "E": "/api/me получил 200, UI сломался после авторизации",
    "F": "запросы не дошли до production",
    "G": "загружен старый asset/cache",
    "H": "открыт не тот бот или не тот URL",
    "ok_pending_soak": "/api/me 200 — успех (нужен soak ≥60с)",
}


def write_diag_event(record: dict[str, Any]) -> bool:
    """Append one sanitized JSON line. Never raises to callers."""
    try:
        path = diag_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = sanitize_record(record)
        if "ts" not in clean:
            clean["ts"] = utc_now_iso()
        line = json.dumps(clean, ensure_ascii=False, separators=(",", ":"))
        with _lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
        return True
    except Exception:
        logger.debug("miniapp diag write failed", exc_info=True)
        return False
