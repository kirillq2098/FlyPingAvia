"""RL-03: persistent heartbeat компонентов в БД."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from flypingavia.db.models import SystemRuntimeState
from flypingavia.monitoring.keys import COMPONENT_PRICE_CHECKER, sanitize_error_summary


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def get_runtime_state(
    session: AsyncSession, *, component_key: str = COMPONENT_PRICE_CHECKER
) -> SystemRuntimeState | None:
    return await session.get(SystemRuntimeState, component_key)


async def _ensure(
    session: AsyncSession, *, component_key: str
) -> SystemRuntimeState:
    row = await session.get(SystemRuntimeState, component_key)
    if row is None:
        row = SystemRuntimeState(component_key=component_key)
        session.add(row)
        await session.flush()
    return row


async def mark_checker_started(
    session: AsyncSession,
    *,
    at: datetime,
    component_key: str = COMPONENT_PRICE_CHECKER,
) -> None:
    row = await _ensure(session, component_key=component_key)
    row.last_started_at = _aware(at)
    row.updated_at = _aware(at)
    await session.flush()


async def mark_checker_success(
    session: AsyncSession,
    *,
    at: datetime,
    component_key: str = COMPONENT_PRICE_CHECKER,
) -> None:
    now = _aware(at)
    row = await _ensure(session, component_key=component_key)
    row.last_completed_at = now
    row.last_success_at = now
    row.updated_at = now
    await session.flush()


async def mark_checker_error(
    session: AsyncSession,
    *,
    at: datetime,
    summary: str,
    component_key: str = COMPONENT_PRICE_CHECKER,
) -> None:
    now = _aware(at)
    row = await _ensure(session, component_key=component_key)
    row.last_completed_at = now
    row.last_error_at = now
    row.last_error_summary = sanitize_error_summary(summary)
    row.updated_at = now
    await session.flush()
