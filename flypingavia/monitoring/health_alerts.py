"""RL-03: сервис инцидентов (threshold + cooldown, без отправки)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from flypingavia.db.models import SystemHealthIncident
from flypingavia.monitoring.keys import sanitize_error_summary

logger = logging.getLogger(__name__)

STATUS_OPEN = "open"
STATUS_RECOVERED = "recovered"


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class IncidentNotificationDecision:
    should_notify: bool
    kind: str  # failure | recovery | none
    incident: SystemHealthIncident | None = None
    failure_count: int = 0
    was_previously_notified: bool = False


async def get_open_incident(
    session: AsyncSession, *, incident_key: str
) -> SystemHealthIncident | None:
    result = await session.execute(
        select(SystemHealthIncident)
        .where(
            SystemHealthIncident.incident_key == incident_key,
            SystemHealthIncident.status == STATUS_OPEN,
        )
        .order_by(SystemHealthIncident.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_open_incidents(session: AsyncSession) -> int:
    from sqlalchemy import func

    result = await session.execute(
        select(func.count())
        .select_from(SystemHealthIncident)
        .where(SystemHealthIncident.status == STATUS_OPEN)
    )
    return int(result.scalar_one() or 0)


async def report_failure(
    session: AsyncSession,
    *,
    incident_key: str,
    summary: str,
    occurred_at: datetime,
    failure_threshold: int,
    cooldown_seconds: int,
    error_code: str | None = None,
) -> IncidentNotificationDecision:
    """Зафиксировать сбой; решить, нужно ли уведомление (без отправки)."""
    now = _aware(occurred_at)
    safe = sanitize_error_summary(summary)
    code = (error_code or incident_key)[:64]

    incident = await get_open_incident(session, incident_key=incident_key)
    if incident is None:
        incident = SystemHealthIncident(
            incident_key=incident_key,
            status=STATUS_OPEN,
            first_failed_at=now,
            last_failed_at=now,
            failure_count=1,
            last_error_code=code,
            last_error_summary=safe,
            created_at=now,
            updated_at=now,
        )
        session.add(incident)
        await session.flush()
        logger.info("Health incident opened: key=%s", incident_key)
    else:
        incident.failure_count = int(incident.failure_count or 0) + 1
        incident.last_failed_at = now
        incident.last_error_code = code
        incident.last_error_summary = safe
        incident.updated_at = now
        await session.flush()

    count = int(incident.failure_count or 0)
    previously = incident.last_notified_at is not None

    if count < max(1, failure_threshold):
        return IncidentNotificationDecision(
            should_notify=False,
            kind="none",
            incident=incident,
            failure_count=count,
            was_previously_notified=previously,
        )

    if incident.last_notified_at is None:
        return IncidentNotificationDecision(
            should_notify=True,
            kind="failure",
            incident=incident,
            failure_count=count,
            was_previously_notified=False,
        )

    last = _aware(incident.last_notified_at)
    if (now - last).total_seconds() >= max(60, cooldown_seconds):
        return IncidentNotificationDecision(
            should_notify=True,
            kind="failure",
            incident=incident,
            failure_count=count,
            was_previously_notified=True,
        )

    return IncidentNotificationDecision(
        should_notify=False,
        kind="none",
        incident=incident,
        failure_count=count,
        was_previously_notified=True,
    )


async def mark_notified(
    session: AsyncSession,
    *,
    incident_id: int,
    notified_at: datetime,
) -> None:
    incident = await session.get(SystemHealthIncident, incident_id)
    if incident is None:
        return
    incident.last_notified_at = _aware(notified_at)
    incident.updated_at = _aware(notified_at)
    await session.flush()
    logger.info(
        "Health incident notification sent: key=%s",
        incident.incident_key,
    )


async def report_recovery(
    session: AsyncSession,
    *,
    incident_key: str,
    recovered_at: datetime,
) -> IncidentNotificationDecision:
    """Закрыть open-инцидент; notify только если был failure alert."""
    now = _aware(recovered_at)
    incident = await get_open_incident(session, incident_key=incident_key)
    if incident is None:
        return IncidentNotificationDecision(should_notify=False, kind="none")

    previously = incident.last_notified_at is not None
    count = int(incident.failure_count or 0)
    incident.status = STATUS_RECOVERED
    incident.recovered_at = now
    incident.updated_at = now
    await session.flush()
    logger.info("Health incident recovered: key=%s", incident_key)

    if not previously:
        return IncidentNotificationDecision(
            should_notify=False,
            kind="none",
            incident=incident,
            failure_count=count,
            was_previously_notified=False,
        )

    return IncidentNotificationDecision(
        should_notify=True,
        kind="recovery",
        incident=incident,
        failure_count=count,
        was_previously_notified=True,
    )
