"""RL-03: классификация ошибок Telegram send (user vs system)."""

from __future__ import annotations

from flypingavia.monitoring.keys import sanitize_error_summary

USER = "user"
SYSTEM = "system"


def classify_telegram_send_error(exc: BaseException) -> str:
    """Вернуть 'user' или 'system'. Не раскрывать token."""
    name = type(exc).__name__.lower()
    msg = sanitize_error_summary(str(exc), limit=200).lower()

    user_markers = (
        "blocked by the user",
        "bot was blocked",
        "forbidden: bot was blocked",
        "chat not found",
        "user is deactivated",
        "user deactivated",
        "bot can't initiate conversation",
        "have no rights to send",
        "forbidden: bot can't send messages to bots",
    )
    if any(m in msg for m in user_markers):
        return USER
    if "forbidden" in name and ("block" in msg or "chat not found" in msg):
        return USER

    system_markers = (
        "timeout",
        "timed out",
        "connection",
        "network",
        "temporary failure",
        "bad gateway",
        "service unavailable",
        "internal server error",
        "retry after",
        "retry_after",
        "too many requests",
        "flood",
        "server error",
        "5xx",
    )
    if any(m in msg for m in system_markers):
        return SYSTEM
    if "network" in name or "timeout" in name or "retryafter" in name:
        return SYSTEM
    # неизвестное — считаем системным (осторожнее для spam, но threshold защищает)
    if "telegram" in name or "client" in name:
        return SYSTEM
    return SYSTEM


def is_user_telegram_error(exc: BaseException) -> bool:
    return classify_telegram_send_error(exc) == USER
