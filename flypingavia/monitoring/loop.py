"""RL-03: фоновый health monitor loop."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from aiogram import Bot
from sqlalchemy import func, select, text

from flypingavia.config import Settings
from flypingavia.db.models import Watch
from flypingavia.db.session import session_scope
from flypingavia.monitoring.db_fallback import DatabaseOutageTracker
from flypingavia.monitoring.heartbeat import get_runtime_state
from flypingavia.monitoring.keys import (
    COMPONENT_PRICE_CHECKER,
    INCIDENT_CHECKER_STALLED,
    INCIDENT_DATABASE,
    INCIDENT_READINESS,
    INCIDENT_WEBAPP,
)
from flypingavia.monitoring.notify import (
    notify_failure,
    notify_recovery,
    retry_pending_recoveries,
)
from flypingavia.webapp_url import is_temporary_tunnel_hostname

logger = logging.getLogger(__name__)


class HealthMonitor:
    def __init__(
        self,
        settings: Settings,
        bot: Bot,
        *,
        database_outage: DatabaseOutageTracker | None = None,
    ) -> None:
        self.settings = settings
        self.bot = bot
        self.started_at = datetime.now(timezone.utc)
        self._task: asyncio.Task | None = None
        self.database_outage = database_outage or DatabaseOutageTracker()

    def start(self) -> asyncio.Task:
        self._task = asyncio.create_task(self._run(), name="health-monitor")
        return self._task

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def _run(self) -> None:
        interval = self.settings.health_monitor_interval_seconds
        logger.info("Health monitor started interval=%ss", interval)
        try:
            while True:
                try:
                    await self.run_once()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Health monitor iteration failed")
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("Health monitor stopped")
            raise

    async def run_once(self) -> None:
        now = datetime.now(timezone.utc)
        await self._run_check_safely("pending_recoveries", self._retry_pending_recoveries, now)
        await self._run_check_safely("database", self._check_database, now)
        await self._run_check_safely("checker", self._check_checker_stalled, now)
        await self._run_check_safely("readiness", self._check_readiness, now)
        await self._run_check_safely("webapp", self._check_webapp, now)

    async def _run_check_safely(
        self,
        check_name: str,
        check: Callable[[datetime], Awaitable[None]],
        now: datetime,
    ) -> None:
        try:
            await check(now)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Health check failed: %s", check_name)

    async def _retry_pending_recoveries(self, now: datetime) -> None:
        del now
        await retry_pending_recoveries(self.bot, self.settings)
        await self.database_outage.retry_pending_recovery(
            self.bot, self.settings, now=datetime.now(timezone.utc)
        )

    async def _check_database(self, now: datetime) -> None:
        try:
            async with session_scope() as session:
                await session.execute(text("SELECT 1"))
        except Exception as exc:
            # Нельзя писать incident в недоступную БД — только in-memory fallback.
            await self.database_outage.report_failure(
                self.bot,
                self.settings,
                summary=type(exc).__name__,
                occurred_at=now,
            )
            return

        if self.database_outage.has_outage():
            await self.database_outage.report_recovery(
                self.bot, self.settings, recovered_at=now
            )
            return

        await notify_recovery(
            self.bot, self.settings, incident_key=INCIDENT_DATABASE, recovered_at=now
        )

    async def _check_checker_stalled(self, now: datetime) -> None:
        grace = self.settings.health_startup_grace_seconds
        if (now - self.started_at).total_seconds() < grace:
            return

        async with session_scope() as session:
            active = int(
                (
                    await session.execute(
                        select(func.count())
                        .select_from(Watch)
                        .where(Watch.is_active.is_(True))
                    )
                ).scalar_one()
                or 0
            )
            state = await get_runtime_state(
                session, component_key=COMPONENT_PRICE_CHECKER
            )

        if active <= 0:
            await notify_recovery(
                self.bot,
                self.settings,
                incident_key=INCIDENT_CHECKER_STALLED,
                recovered_at=now,
            )
            return

        stale_after = self.settings.effective_checker_stale_after_seconds
        last = None
        if state is not None:
            last = state.last_completed_at or state.last_success_at
        if last is None:
            # ещё не было ни одной проверки после старта — stalled после stale_after от start
            age = (now - self.started_at).total_seconds()
            if age >= stale_after:
                await notify_failure(
                    self.bot,
                    self.settings,
                    incident_key=INCIDENT_CHECKER_STALLED,
                    summary="no checker heartbeat",
                    occurred_at=now,
                )
            return

        from flypingavia.monitoring.health_alerts import _aware

        age = (now - _aware(last)).total_seconds()
        if age >= stale_after:
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_CHECKER_STALLED,
                summary="checker heartbeat stale",
                occurred_at=now,
            )
        else:
            await notify_recovery(
                self.bot,
                self.settings,
                incident_key=INCIDENT_CHECKER_STALLED,
                recovered_at=now,
            )

    async def _check_readiness(self, now: datetime) -> None:
        issues = self.settings.readiness_issues()
        if issues:
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_READINESS,
                summary=",".join(issues)[:200],
                occurred_at=now,
            )
        else:
            await notify_recovery(
                self.bot,
                self.settings,
                incident_key=INCIDENT_READINESS,
                recovered_at=now,
            )

    async def _check_webapp(self, now: datetime) -> None:
        if not self.settings.is_production:
            await notify_recovery(
                self.bot, self.settings, incident_key=INCIDENT_WEBAPP, recovered_at=now
            )
            return
        url = (self.settings.webapp_url or "").strip()
        if not url:
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_WEBAPP,
                summary="webapp url missing",
                occurred_at=now,
            )
            return
        parsed = urlparse(url)
        if parsed.scheme != "https" or is_temporary_tunnel_hostname(parsed.hostname):
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_WEBAPP,
                summary="webapp url invalid for production",
                occurred_at=now,
            )
            return

        # Не бить сам себя по публичному URL: local health достаточно в том же процессе.
        # Проверяем, что origin настроен и локальный /api/health отвечает.
        try:
            timeout = self.settings.webapp_healthcheck_timeout_seconds
            local = f"http://127.0.0.1:{self.settings.webapp_port}/api/health"
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.get(local)
            if resp.status_code == 200:
                await notify_recovery(
                    self.bot,
                    self.settings,
                    incident_key=INCIDENT_WEBAPP,
                    recovered_at=now,
                )
            else:
                await notify_failure(
                    self.bot,
                    self.settings,
                    incident_key=INCIDENT_WEBAPP,
                    summary=f"local health http {resp.status_code}",
                    occurred_at=now,
                )
        except Exception as exc:
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_WEBAPP,
                summary=type(exc).__name__,
                occurred_at=now,
            )
