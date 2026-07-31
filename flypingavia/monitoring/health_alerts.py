"""RL-03: сервис инцидентов (threshold + cooldown; recovery pending до доставки)."""

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
STATUS_RECOVERY_PENDING = "recovery_pending"
STATUS_RECOVERED = "recovered"

ACTIVE_STATUSES = (STATUS_OPEN, STATUS_RECOVERY_PENDING)


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
    """Открытый (ещё не recovered) инцидент — open или recovery_pending."""
    result = await session.execute(
        select(SystemHealthIncident)
        .where(
            SystemHealthIncident.incident_key == incident_key,
            SystemHealthIncident.status.in_(ACTIVE_STATUSES),
        )
        .order_by(SystemHealthIncident.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_open_incidents(session: AsyncSession) -> int:
    """Число активных инцидентов (open + recovery_pending) для /api/ready."""
    from sqlalchemy import func

    result = await session.execute(
        select(func.count())
        .select_from(SystemHealthIncident)
        .where(SystemHealthIncident.status.in_(ACTIVE_STATUSES))
    )
    return int(result.scalar_one() or 0)


async def list_pending_recoveries(session: AsyncSession) -> list[SystemHealthIncident]:
    result = await session.execute(
        select(SystemHealthIncident)
        .where(SystemHealthIncident.status == STATUS_RECOVERY_PENDING)
        .order_by(SystemHealthIncident.id.asc())
    )
    return list(result.scalars().all())


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
    if incident is not None and incident.status == STATUS_RECOVERY_PENDING:
        # Сбой после детекта recovery — вернуть в open
        incident.status = STATUS_OPEN
        incident.recovered_at = None
        incident.recovery_notified_at = None

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


async def detect_recovery(
    session: AsyncSession,
    *,
    incident_key: str,
    recovered_at: datetime,
) -> IncidentNotificationDecision:
    """Отметить восстановление как recovery_pending (не закрывать до доставки)."""
    now = _aware(recovered_at)
    incident = await get_open_incident(session, incident_key=incident_key)
    if incident is None:
        return IncidentNotificationDecision(should_notify=False, kind="none")

    if incident.status == STATUS_RECOVERY_PENDING:
        # Уже pending — повторить send, если failure был и recovery ещё не доставлен
        previously = incident.last_notified_at is not None
        if previously and incident.recovery_notified_at is None:
            return IncidentNotificationDecision(
                should_notify=True,
                kind="recovery",
                incident=incident,
                failure_count=int(incident.failure_count or 0),
                was_previously_notified=True,
            )
        return IncidentNotificationDecision(
            should_notify=False,
            kind="none",
            incident=incident,
            failure_count=int(incident.failure_count or 0),
            was_previously_notified=previously,
        )

    previously = incident.last_notified_at is not None
    count = int(incident.failure_count or 0)

    if not previously:
        # Failure alert не уходил — закрываем без recovery notification
        incident.status = STATUS_RECOVERED
        incident.recovered_at = now
        incident.recovery_notified_at = now
        incident.updated_at = now
        await session.flush()
        logger.info("Health incident recovered: key=%s (no prior alert)", incident_key)
        return IncidentNotificationDecision(
            should_notify=False,
            kind="none",
            incident=incident,
            failure_count=count,
            was_previously_notified=False,
        )

    incident.status = STATUS_RECOVERY_PENDING
    incident.recovered_at = now
    incident.updated_at = now
    await session.flush()
    logger.info("Health incident recovery pending: key=%s", incident_key)
    return IncidentNotificationDecision(
        should_notify=True,
        kind="recovery",
        incident=incident,
        failure_count=count,
        was_previously_notified=True,
    )


# Совместимость со старым именем в тестах/импортах
async def report_recovery(
    session: AsyncSession,
    *,
    incident_key: str,
    recovered_at: datetime,
) -> IncidentNotificationDecision:
    """Alias → detect_recovery (не закрывает окончательно до mark_recovery_notified)."""
    return await detect_recovery(
        session, incident_key=incident_key, recovered_at=recovered_at
    )


async def mark_recovery_notified(
    session: AsyncSession,
    *,
    incident_id: int,
    notified_at: datetime,
) -> None:
    """Окончательно закрыть incident после успешной доставки recovery."""
    incident = await session.get(SystemHealthIncident, incident_id)
    if incident is None:
        return
    now = _aware(notified_at)
    incident.status = STATUS_RECOVERED
    if incident.recovered_at is None:
        incident.recovered_at = now
    incident.recovery_notified_at = now
    incident.updated_at = now
    await session.flush()
    logger.info("Health incident recovered: key=%s", incident.incident_key)


async def sync_recovered_incident_from_fallback(
    session: AsyncSession,
    *,
    incident_key: str,
    first_failed_at: datetime,
    last_failed_at: datetime,
    recovered_at: datetime,
    failure_count: int,
    last_notified_at: datetime | None,
    summary: str = "database unavailable",
) -> SystemHealthIncident:
    """Записать исторический recovered incident после DB outage fallback."""
    now = _aware(recovered_at)
    existing = await get_open_incident(session, incident_key=incident_key)
    if existing is not None:
        existing.status = STATUS_RECOVERED
        existing.first_failed_at = _aware(first_failed_at)
        existing.last_failed_at = _aware(last_failed_at)
        existing.recovered_at = now
        existing.failure_count = max(int(existing.failure_count or 0), int(failure_count))
        if last_notified_at is not None:
            existing.last_notified_at = _aware(last_notified_at)
            existing.recovery_notified_at = now
        else:
            existing.recovery_notified_at = now
        existing.last_error_summary = sanitize_error_summary(summary)
        existing.updated_at = now
        await session.flush()
        return existing

    row = SystemHealthIncident(
        incident_key=incident_key,
        status=STATUS_RECOVERED,
        first_failed_at=_aware(first_failed_at),
        last_failed_at=_aware(last_failed_at),
        recovered_at=now,
        last_notified_at=_aware(last_notified_at) if last_notified_at else None,
        recovery_notified_at=now if last_notified_at else now,
        failure_count=int(failure_count),
        last_error_code=incident_key,
        last_error_summary=sanitize_error_summary(summary),
        created_at=_aware(first_failed_at),
        updated_at=now,
    )
    session.add(row)
    await session.flush()
    return row
