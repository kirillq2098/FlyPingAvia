"""RL-03: in-memory fallback для database_unavailable (когда БД недоступна)."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from aiogram import Bot

from flypingavia.config import Settings
from flypingavia.monitoring.admin_notify import maybe_send_admin_alert
from flypingavia.monitoring.formatters import (
    format_admin_failure_alert,
    format_admin_recovery_alert,
)
from flypingavia.monitoring.keys import INCIDENT_DATABASE, sanitize_error_summary

logger = logging.getLogger(__name__)


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass
class DatabaseOutageState:
    first_failed_at: datetime | None = None
    last_failed_at: datetime | None = None
    failure_count: int = 0
    last_notified_at: datetime | None = None
    failure_notification_sent: bool = False
    recovery_pending: bool = False
    recovered_at: datetime | None = None
    last_error_summary: str = "database unavailable"


@dataclass
class DatabaseOutageTracker:
    """Process-local состояние только для DB outage.

    Полный restart процесса во время outage сбрасывает счётчик — это ожидаемо.
    После восстановления БД — source of truth снова таблица system_health_incidents.
    """

    _state: DatabaseOutageState = field(default_factory=DatabaseOutageState)

    @property
    def state(self) -> DatabaseOutageState:
        return self._state

    def has_outage(self) -> bool:
        """True, пока process-local outage не очищен после recovery/sync."""
        return self._state.first_failed_at is not None

    def clear(self) -> None:
        self._state = DatabaseOutageState()

    async def report_failure(
        self,
        bot: Bot | None,
        settings: Settings,
        *,
        summary: str,
        occurred_at: datetime,
    ) -> None:
        now = _aware(occurred_at)
        safe = sanitize_error_summary(summary)
        st = self._state
        if st.first_failed_at is None:
            st.first_failed_at = now
            st.failure_count = 1
            logger.info("Health incident opened: key=%s (fallback)", INCIDENT_DATABASE)
        else:
            # Новый сбой после pending recovery
            if st.recovery_pending:
                st.recovery_pending = False
                st.recovered_at = None
            st.failure_count = int(st.failure_count or 0) + 1
        st.last_failed_at = now
        st.last_error_summary = safe

        threshold = max(1, int(settings.admin_alert_failure_threshold))
        cooldown = max(60, int(settings.admin_alert_cooldown_seconds))
        if st.failure_count < threshold:
            return

        should = False
        if st.last_notified_at is None:
            should = True
        else:
            elapsed = (now - _aware(st.last_notified_at)).total_seconds()
            if elapsed >= cooldown:
                should = True
        if not should or bot is None:
            return

        text = format_admin_failure_alert(
            incident_key=INCIDENT_DATABASE,
            failure_count=st.failure_count,
            first_failed_at=st.first_failed_at or now,
            display_timezone=settings.display_tz,
            summary=safe,
        )
        ok = await maybe_send_admin_alert(bot, settings, text=text)
        if ok:
            st.last_notified_at = now
            st.failure_notification_sent = True
            logger.info(
                "Health incident notification sent: key=%s (fallback)",
                INCIDENT_DATABASE,
            )

    async def report_recovery(
        self,
        bot: Bot | None,
        settings: Settings,
        *,
        recovered_at: datetime,
    ) -> None:
        st = self._state
        if st.first_failed_at is None:
            return

        now = _aware(recovered_at)

        # Нет prior failure alert — просто очистить без recovery
        if not st.failure_notification_sent:
            await self._sync_history_to_db(settings, recovered_at=now, sent_recovery=False)
            self.clear()
            return

        st.recovery_pending = True
        st.recovered_at = now

        if bot is None:
            return

        text = format_admin_recovery_alert(
            incident_key=INCIDENT_DATABASE,
            first_failed_at=st.first_failed_at,
            recovered_at=now,
            failure_count=st.failure_count,
            display_timezone=settings.display_tz,
        )
        ok = await maybe_send_admin_alert(bot, settings, text=text)
        if not ok:
            # pending остаётся — повтор на следующей iteration
            return

        await self._sync_history_to_db(settings, recovered_at=now, sent_recovery=True)
        self.clear()
        logger.info("Health incident recovered: key=%s (fallback)", INCIDENT_DATABASE)

    async def retry_pending_recovery(
        self,
        bot: Bot | None,
        settings: Settings,
        *,
        now: datetime,
    ) -> None:
        st = self._state
        if not st.recovery_pending or not st.failure_notification_sent:
            return
        await self.report_recovery(bot, settings, recovered_at=st.recovered_at or now)

    async def _sync_history_to_db(
        self,
        settings: Settings,
        *,
        recovered_at: datetime,
        sent_recovery: bool,
    ) -> None:
        st = self._state
        if st.first_failed_at is None:
            return
        try:
            from flypingavia.db.session import session_scope
            from flypingavia.monitoring import health_alerts as incidents

            async with session_scope() as session:
                await incidents.sync_recovered_incident_from_fallback(
                    session,
                    incident_key=INCIDENT_DATABASE,
                    first_failed_at=st.first_failed_at,
                    last_failed_at=st.last_failed_at or recovered_at,
                    recovered_at=recovered_at,
                    failure_count=st.failure_count,
                    last_notified_at=st.last_notified_at if sent_recovery or st.failure_notification_sent else None,
                    summary=st.last_error_summary,
                )
        except Exception:
            logger.warning(
                "Failed to sync database outage history to DB after recovery",
                exc_info=True,
            )
