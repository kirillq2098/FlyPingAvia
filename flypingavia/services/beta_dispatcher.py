"""Closed Beta Phase A: durable job dispatcher (no Travelpayouts / price checks)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

from flypingavia.config import Settings
from flypingavia.db.models import BetaJob
from flypingavia.db.session import session_scope
from flypingavia.services import beta_repo as beta

logger = logging.getLogger(__name__)


async def run_beta_dispatcher(*, bot: Bot, settings: Settings) -> None:
    """APScheduler entry: process due beta_jobs. Never calls price providers."""
    if not settings.beta_enabled:
        return
    async with session_scope() as session:
        if await beta.is_beta_paused(session):
            return
        jobs = await beta.claim_due_jobs(session)
        job_meta = [
            {
                "id": j.id,
                "type": j.job_type,
                "user_id": j.user_id,
                "attempts": j.attempts,
            }
            for j in jobs
        ]
    for meta in job_meta:
        try:
            await _process_job(bot=bot, settings=settings, meta=meta)
        except Exception:
            logger.exception("beta_dispatcher job_id=%s failed", meta["id"])
            async with session_scope() as session:
                await beta.finish_job(
                    session,
                    job_id=meta["id"],
                    status="error",
                    error_summary="dispatcher_exception",
                )


async def _process_job(*, bot: Bot, settings: Settings, meta: dict) -> None:
    _ = settings
    job_type = meta["type"]
    job_id = int(meta["id"])
    user_id = meta["user_id"]
    if job_type != beta.JOB_SURVEY_A or user_id is None:
        async with session_scope() as session:
            await beta.finish_job(
                session, job_id=job_id, status="cancelled", error_summary="unknown_job"
            )
        return

    user_id = int(user_id)
    async with session_scope() as session:
        part = await beta.get_participant(session, user_id=user_id)
        if not beta.messaging_allowed(part):
            await beta.finish_job(
                session, job_id=job_id, status="cancelled", error_summary="opt_out_or_blocked"
            )
            return
        if part is not None and part.consent_at is None:
            job_row = await session.get(BetaJob, job_id)
            if job_row is not None:
                await beta.requeue_job(
                    session,
                    job=job_row,
                    run_at=datetime.now(timezone.utc) + timedelta(minutes=15),
                    error_summary="awaiting_consent",
                )
            return
        tg_id = await beta.get_user_telegram_id(session, user_id=user_id)
        if tg_id is None:
            await beta.finish_job(
                session, job_id=job_id, status="error", error_summary="missing_telegram_id"
            )
            return

    from flypingavia.bot import keyboards as kb

    text = (
        "Короткий опрос Closed Beta (1–2 минуты).\n\n"
        "1) Всё получилось создать подписку и разобраться?"
    )
    try:
        await bot.send_message(
            tg_id,
            text,
            reply_markup=kb.beta_survey_result_kb(),
        )
    except TelegramForbiddenError:
        async with session_scope() as session:
            await beta.mark_participant_blocked(session, user_id=user_id)
            await beta.finish_job(
                session, job_id=job_id, status="cancelled", error_summary="telegram_forbidden"
            )
        return
    except TelegramBadRequest as exc:
        async with session_scope() as session:
            if int(meta["attempts"]) >= beta.MAX_JOB_ATTEMPTS:
                await beta.finish_job(
                    session,
                    job_id=job_id,
                    status="error",
                    error_summary=str(exc),
                )
            else:
                job_row = await session.get(BetaJob, job_id)
                if job_row is not None:
                    job_row.status = "pending"
                    job_row.run_at = datetime.now(timezone.utc) + timedelta(minutes=5)
                    job_row.last_error_summary = beta.safe_error_summary(exc)
        return

    async with session_scope() as session:
        await beta.mark_survey_sent(session, user_id=user_id)
        await beta.finish_job(session, job_id=job_id, status="done")
