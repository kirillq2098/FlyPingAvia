"""RL-03: apply failure/recovery decisions + optional admin notify."""

from __future__ import annotations

from datetime import datetime, timezone

from aiogram import Bot

from flypingavia.config import Settings
from flypingavia.db.session import session_scope
from flypingavia.monitoring import health_alerts as incidents
from flypingavia.monitoring.admin_notify import maybe_send_admin_alert
from flypingavia.monitoring.formatters import (
    format_admin_failure_alert,
    format_admin_recovery_alert,
)


async def notify_failure(
    bot: Bot | None,
    settings: Settings,
    *,
    incident_key: str,
    summary: str,
    occurred_at: datetime | None = None,
) -> None:
    now = occurred_at or datetime.now(timezone.utc)
    async with session_scope() as session:
        decision = await incidents.report_failure(
            session,
            incident_key=incident_key,
            summary=summary,
            occurred_at=now,
            failure_threshold=settings.admin_alert_failure_threshold,
            cooldown_seconds=settings.admin_alert_cooldown_seconds,
        )
        incident_id = decision.incident.id if decision.incident else None
        first_failed = (
            decision.incident.first_failed_at if decision.incident else now
        )
        count = decision.failure_count
        summary_safe = (
            decision.incident.last_error_summary if decision.incident else summary
        )

    if not decision.should_notify or bot is None or incident_id is None:
        return

    text = format_admin_failure_alert(
        incident_key=incident_key,
        failure_count=count,
        first_failed_at=first_failed,
        display_timezone=settings.display_tz,
        summary=summary_safe,
    )
    ok = await maybe_send_admin_alert(bot, settings, text=text)
    if ok:
        async with session_scope() as session:
            await incidents.mark_notified(
                session, incident_id=incident_id, notified_at=now
            )


async def notify_recovery(
    bot: Bot | None,
    settings: Settings,
    *,
    incident_key: str,
    recovered_at: datetime | None = None,
) -> None:
    """Detect recovery → pending; finalize только после успешной доставки."""
    now = recovered_at or datetime.now(timezone.utc)
    async with session_scope() as session:
        decision = await incidents.detect_recovery(
            session,
            incident_key=incident_key,
            recovered_at=now,
        )
        if not decision.should_notify or decision.incident is None:
            return
        incident_id = decision.incident.id
        first_failed = decision.incident.first_failed_at
        recovered_ts = decision.incident.recovered_at or now
        count = decision.failure_count

    if bot is None:
        return

    text = format_admin_recovery_alert(
        incident_key=incident_key,
        first_failed_at=first_failed,
        recovered_at=recovered_ts,
        failure_count=count,
        display_timezone=settings.display_tz,
    )
    ok = await maybe_send_admin_alert(bot, settings, text=text)
    if ok:
        async with session_scope() as session:
            await incidents.mark_recovery_notified(
                session, incident_id=incident_id, notified_at=now
            )


async def retry_pending_recoveries(bot: Bot | None, settings: Settings) -> None:
    """Повторить недоставленные recovery после restart / Telegram glitch."""
    if bot is None:
        return
    async with session_scope() as session:
        pending = await incidents.list_pending_recoveries(session)
        snapshots = [
            (
                row.id,
                row.incident_key,
                row.first_failed_at,
                row.recovered_at,
                int(row.failure_count or 0),
            )
            for row in pending
            if row.recovery_notified_at is None and row.last_notified_at is not None
        ]

    now = datetime.now(timezone.utc)
    for incident_id, key, first_failed, recovered_ts, count in snapshots:
        text = format_admin_recovery_alert(
            incident_key=key,
            first_failed_at=first_failed,
            recovered_at=recovered_ts or now,
            failure_count=count,
            display_timezone=settings.display_tz,
        )
        ok = await maybe_send_admin_alert(bot, settings, text=text)
        if ok:
            async with session_scope() as session:
                await incidents.mark_recovery_notified(
                    session, incident_id=incident_id, notified_at=now
                )
