"""RL-03: тексты служебных health-алертов."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

from flypingavia.monitoring.keys import (
    COMPONENT_LABELS,
    STATUS_LABELS,
    sanitize_error_summary,
)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt_local(dt: datetime, tz: ZoneInfo) -> str:
    local = _aware(dt).astimezone(tz)
    # 31 июля 2026, 00:15
    months = (
        "",
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )
    return f"{local.day} {months[local.month]} {local.year}, {local.hour:02d}:{local.minute:02d}"


def _duration_label(delta: timedelta) -> str:
    total = max(0, int(delta.total_seconds()))
    if total < 60:
        return f"{total} сек."
    minutes = total // 60
    if minutes < 60:
        return f"{minutes} мин."
    hours = minutes // 60
    rem = minutes % 60
    if rem == 0:
        return f"{hours} ч."
    return f"{hours} ч. {rem} мин."


def format_admin_failure_alert(
    *,
    incident_key: str,
    failure_count: int,
    first_failed_at: datetime,
    display_timezone: ZoneInfo,
    summary: str | None = None,
) -> str:
    component = COMPONENT_LABELS.get(incident_key, "Компонент")
    state = STATUS_LABELS.get(incident_key, "сбой")
    started = _fmt_local(first_failed_at, display_timezone)
    safe_key = escape(str(incident_key))
    lines = [
        "🚨 Проблема в FlyPing",
        "",
        f"Компонент: {escape(component)}",
        f"Состояние: {escape(state)}",
        f"Начало: {escape(started)}",
        f"Повторных ошибок: {int(failure_count)}",
    ]
    if summary:
        cleaned = sanitize_error_summary(summary, limit=200)
        if cleaned and cleaned != "error":
            lines.append(f"Детали: {escape(cleaned)}")
    lines.append("")
    lines.append(f"Код: <code>{safe_key}</code>")
    return "\n".join(lines)


def format_admin_recovery_alert(
    *,
    incident_key: str,
    first_failed_at: datetime,
    recovered_at: datetime,
    failure_count: int,
    display_timezone: ZoneInfo,
) -> str:
    component = COMPONENT_LABELS.get(incident_key, "Компонент")
    start = _fmt_local(first_failed_at, display_timezone)
    end = _fmt_local(recovered_at, display_timezone)
    dur = _duration_label(_aware(recovered_at) - _aware(first_failed_at))
    return "\n".join(
        [
            "✅ FlyPing восстановился",
            "",
            f"Компонент: {escape(component)}",
            f"Сбой начался: {escape(start)}",
            f"Восстановление: {escape(end)}",
            f"Продолжительность: {escape(dur)}",
            f"Ошибок за период: {int(failure_count)}",
        ]
    )


def format_admin_health_status(
    *,
    db_ok: bool,
    checker_ok: bool,
    provider_ok: bool,
    webapp_ok: bool | None,
    open_incidents: int,
    last_success_at: datetime | None,
    display_timezone: ZoneInfo,
) -> str:
    def flag(ok: bool | None) -> str:
        if ok is None:
            return "не применимо"
        return "работает" if ok else "проблема"

    last = "—"
    if last_success_at is not None:
        last = _fmt_local(last_success_at, display_timezone)
    return "\n".join(
        [
            "<b>Состояние FlyPing</b>",
            "",
            f"База данных: {flag(db_ok)}",
            f"Checker: {flag(checker_ok)}",
            f"Провайдер: {flag(provider_ok)}",
            f"Mini App: {flag(webapp_ok)}",
            f"Открытых инцидентов: {int(open_incidents)}",
            f"Последняя успешная проверка: {escape(last)}",
        ]
    )
