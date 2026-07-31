"""RL-03: scheduler wrapper — unexpected crash → checker_crashed."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot

from flypingavia.config import Settings
from flypingavia.db.session import session_scope
from flypingavia.monitoring.heartbeat import mark_checker_error
from flypingavia.monitoring.keys import INCIDENT_CHECKER_CRASHED
from flypingavia.monitoring.notify import notify_failure, notify_recovery
from flypingavia.services.checker import PriceChecker

logger = logging.getLogger(__name__)


async def run_checker_job(
    checker: PriceChecker,
    bot: Bot,
    settings: Settings,
) -> int:
    """Обёртка для APScheduler: unexpected exception → checker_crashed."""
    try:
        result = await checker.run_once()
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.exception("Price checker crashed unexpectedly")
        now = datetime.now(timezone.utc)
        try:
            async with session_scope() as session:
                await mark_checker_error(
                    session, at=now, summary=type(exc).__name__
                )
        except Exception:
            logger.warning("Failed to update checker heartbeat after crash", exc_info=True)
        try:
            await notify_failure(
                bot,
                settings,
                incident_key=INCIDENT_CHECKER_CRASHED,
                summary=type(exc).__name__,
                occurred_at=now,
            )
        except Exception:
            logger.warning("Failed to record checker_crashed incident", exc_info=True)
        return 0
    else:
        try:
            await notify_recovery(
                bot,
                settings,
                incident_key=INCIDENT_CHECKER_CRASHED,
            )
        except Exception:
            logger.warning("Failed to recover checker_crashed incident", exc_info=True)
        return result
