"""Closed Beta Phase A: schedule Survey A after first watch (bot + API)."""

from __future__ import annotations

import logging

from flypingavia.config import Settings
from flypingavia.db.session import session_scope
from flypingavia.services import beta_repo as beta

logger = logging.getLogger(__name__)


async def maybe_schedule_survey_a_for_user(
    *,
    user_id: int,
    settings: Settings,
) -> bool:
    """Идемпотентно запланировать Survey A. Не блокирует создание watch."""
    if not settings.beta_enabled:
        return False
    try:
        async with session_scope() as session:
            return await beta.schedule_survey_a(
                session,
                user_id=user_id,
                delay_seconds=settings.beta_survey_a_delay_seconds,
            )
    except Exception:
        logger.exception("Failed to schedule beta survey A user_id=%s", user_id)
        return False
