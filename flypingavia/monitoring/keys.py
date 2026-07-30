"""RL-03: ключи инцидентов и безопасная нормализация summary."""

from __future__ import annotations

import re
from html import unescape

INCIDENT_DATABASE = "database_unavailable"
INCIDENT_PROVIDER = "provider_unavailable"
INCIDENT_CHECKER_STALLED = "checker_stalled"
INCIDENT_CHECKER_CRASHED = "checker_crashed"
INCIDENT_TELEGRAM = "telegram_delivery_failure"
INCIDENT_WEBAPP = "webapp_unavailable"
INCIDENT_READINESS = "readiness_failed"

COMPONENT_LABELS = {
    INCIDENT_DATABASE: "База данных",
    INCIDENT_PROVIDER: "Провайдер цен",
    INCIDENT_CHECKER_STALLED: "Проверка цен",
    INCIDENT_CHECKER_CRASHED: "Проверка цен",
    INCIDENT_TELEGRAM: "Telegram-доставка",
    INCIDENT_WEBAPP: "Mini App",
    INCIDENT_READINESS: "Готовность сервиса",
}

STATUS_LABELS = {
    INCIDENT_DATABASE: "база данных недоступна",
    INCIDENT_PROVIDER: "ошибки ответов провайдера",
    INCIDENT_CHECKER_STALLED: "проверки не выполняются",
    INCIDENT_CHECKER_CRASHED: "фоновая проверка упала",
    INCIDENT_TELEGRAM: "системные сбои доставки",
    INCIDENT_WEBAPP: "публичный URL недоступен",
    INCIDENT_READINESS: "readiness не проходит",
}

COMPONENT_PRICE_CHECKER = "price_checker"
SUMMARY_MAX = 500

_SECRETISH = re.compile(
    r"(?i)(bot[_\s-]?token|api[_\s-]?key|authorization|bearer\s+\S+|"
    r"postgres(ql)?://\S+|mysql://\S+|sqlite:////?\S+|"
    r"\d{8,12}:[A-Za-z0-9_-]{30,})"
)
_QUERY = re.compile(r"\?[^.\s]*")


def sanitize_error_summary(value: str | None, *, limit: int = SUMMARY_MAX) -> str:
    """Обрезать и вычистить summary без traceback/секретов/query."""
    if not value:
        return "error"
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    # убрать типичные traceback-фрагменты
    lower = text.lower()
    idx = lower.find("traceback")
    if idx >= 0:
        text = text[:idx].strip() or "error"
    text = _SECRETISH.sub("[redacted]", text)
    text = _QUERY.sub("", text)
    text = unescape(text)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text or "error"
