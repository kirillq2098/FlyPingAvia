"""Closed Beta Phase A: persistence helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from flypingavia.db.models import BetaBug, BetaJob, BetaParticipant, BetaSurvey, User

if TYPE_CHECKING:
    pass

COMPONENT_BETA_FLOW = "beta_flow"
BETA_PAUSED_MARKER = "paused"
SURVEY_KEY_A = "A"
JOB_SURVEY_A = "survey_a"
MAX_BUGS_PER_DAY = 3
MAX_TEXT = 1000
MAX_DEVICE_NOTE = 128
MAX_JOB_ATTEMPTS = 3


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def clip_text(value: str | None, limit: int = MAX_TEXT) -> str:
    text = (value or "").strip()
    if len(text) > limit:
        return text[:limit]
    return text


def safe_error_summary(exc: BaseException | str, limit: int = 200) -> str:
    raw = str(exc)
    lowered = raw.lower()
    for needle in ("bot_token", "initdata", "authorization", "bearer ", "api_key"):
        if needle in lowered:
            return "telegram_error_redacted"
    return clip_text(raw, limit)


async def get_participant(
    session: AsyncSession, *, user_id: int
) -> BetaParticipant | None:
    return await session.get(BetaParticipant, user_id)


async def upsert_participant(
    session: AsyncSession,
    *,
    user_id: int,
    cohort_code: str,
    now: datetime | None = None,
) -> tuple[BetaParticipant, bool]:
    """Вернуть (participant, created). Повторный вход не дублирует."""
    now = now or _utcnow()
    existing = await get_participant(session, user_id=user_id)
    if existing is not None:
        if existing.status == "blocked":
            return existing, False
        # Re-join after opt-out keeps history; do not auto-clear opt-out
        return existing, False
    row = BetaParticipant(
        user_id=user_id,
        cohort_code=cohort_code.lower(),
        joined_at=now,
        status="active",
    )
    session.add(row)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        existing = await get_participant(session, user_id=user_id)
        assert existing is not None
        return existing, False
    return row, True


async def mark_onboarding_sent(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> None:
    now = now or _utcnow()
    part = await get_participant(session, user_id=user_id)
    if part is None or part.onboarding_sent_at is not None:
        return
    part.onboarding_sent_at = now


async def set_consent(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> bool:
    now = now or _utcnow()
    part = await get_participant(session, user_id=user_id)
    if part is None:
        return False
    if part.consent_at is None:
        part.consent_at = now
    if part.status == "opted_out":
        # Consent after stop does not auto-resume messaging
        pass
    elif part.status != "blocked":
        part.status = "active"
    return True


async def set_opt_out(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> bool:
    now = now or _utcnow()
    part = await get_participant(session, user_id=user_id)
    if part is None:
        return False
    part.messaging_opt_out_at = now
    if part.status != "blocked":
        part.status = "opted_out"
    # Cancel pending survey jobs
    await session.execute(
        update(BetaJob)
        .where(
            BetaJob.user_id == user_id,
            BetaJob.status.in_(("pending", "processing")),
        )
        .values(status="cancelled")
    )
    return True


async def mark_participant_blocked(session: AsyncSession, *, user_id: int) -> None:
    part = await get_participant(session, user_id=user_id)
    if part is None:
        return
    part.status = "blocked"
    await session.execute(
        update(BetaJob)
        .where(
            BetaJob.user_id == user_id,
            BetaJob.status.in_(("pending", "processing")),
        )
        .values(status="cancelled")
    )


def messaging_allowed(part: BetaParticipant | None) -> bool:
    if part is None:
        return False
    if part.status in {"opted_out", "blocked"}:
        return False
    if part.messaging_opt_out_at is not None:
        return False
    return True


async def is_beta_paused(session: AsyncSession) -> bool:
    from flypingavia.db.models import SystemRuntimeState

    row = await session.get(SystemRuntimeState, COMPONENT_BETA_FLOW)
    if row is None:
        return False
    return (row.last_error_summary or "") == BETA_PAUSED_MARKER


async def set_beta_paused(session: AsyncSession, *, paused: bool) -> None:
    from flypingavia.db.models import SystemRuntimeState

    row = await session.get(SystemRuntimeState, COMPONENT_BETA_FLOW)
    now = _utcnow()
    if row is None:
        row = SystemRuntimeState(component_key=COMPONENT_BETA_FLOW)
        session.add(row)
    row.last_error_summary = BETA_PAUSED_MARKER if paused else None
    row.last_completed_at = now
    row.updated_at = now
    await session.flush()


async def schedule_survey_a(
    session: AsyncSession,
    *,
    user_id: int,
    delay_seconds: int,
    now: datetime | None = None,
) -> bool:
    """Создать Survey A + durable job. False если уже есть / нельзя."""
    now = now or _utcnow()
    part = await get_participant(session, user_id=user_id)
    if not messaging_allowed(part):
        return False
    if await is_beta_paused(session):
        return False

    existing = await session.scalar(
        select(BetaSurvey).where(
            BetaSurvey.user_id == user_id,
            BetaSurvey.survey_key == SURVEY_KEY_A,
        )
    )
    if existing is not None:
        return False

    run_at = now + timedelta(seconds=max(30, int(delay_seconds)))
    survey = BetaSurvey(
        user_id=user_id,
        survey_key=SURVEY_KEY_A,
        status="pending",
        scheduled_for=run_at,
    )
    session.add(survey)
    job = BetaJob(
        logical_key=f"survey_a:{user_id}",
        job_type=JOB_SURVEY_A,
        user_id=user_id,
        run_at=run_at,
        status="pending",
        attempts=0,
    )
    session.add(job)
    try:
        async with session.begin_nested():
            await session.flush()
    except IntegrityError:
        return False
    return True


async def claim_due_jobs(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = 20,
) -> list[BetaJob]:
    """Атомарно забрать pending jobs (SQLite-friendly, без SKIP LOCKED)."""
    now = now or _utcnow()
    rows = list(
        (
            await session.execute(
                select(BetaJob)
                .where(
                    BetaJob.status == "pending",
                    BetaJob.run_at <= now,
                    BetaJob.attempts < MAX_JOB_ATTEMPTS,
                )
                .order_by(BetaJob.run_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    claimed: list[BetaJob] = []
    for job in rows:
        result = await session.execute(
            update(BetaJob)
            .where(BetaJob.id == job.id, BetaJob.status == "pending")
            .values(status="processing", attempts=job.attempts + 1)
        )
        if result.rowcount:
            await session.refresh(job)
            claimed.append(job)
    return claimed


async def finish_job(
    session: AsyncSession,
    *,
    job_id: int,
    status: str,
    error_summary: str | None = None,
) -> None:
    values: dict = {"status": status}
    if error_summary is not None:
        values["last_error_summary"] = safe_error_summary(error_summary)
    await session.execute(update(BetaJob).where(BetaJob.id == job_id).values(**values))


async def requeue_job(
    session: AsyncSession,
    *,
    job: BetaJob,
    run_at: datetime,
    error_summary: str | None = None,
) -> None:
    """Вернуть в pending (например ждём consent). Soft-skip: attempt откатывается."""
    job.status = "pending"
    job.run_at = run_at
    if error_summary:
        job.last_error_summary = safe_error_summary(error_summary)
    if job.attempts > 0:
        job.attempts -= 1
    await session.flush()

async def mark_survey_sent(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> None:
    now = now or _utcnow()
    survey = await session.scalar(
        select(BetaSurvey).where(
            BetaSurvey.user_id == user_id,
            BetaSurvey.survey_key == SURVEY_KEY_A,
        )
    )
    if survey is None:
        return
    if survey.status == "pending":
        survey.status = "sent"
        survey.sent_at = now


async def apply_survey_result(
    session: AsyncSession,
    *,
    user_id: int,
    result: str | None = None,
    clarity_score: int | None = None,
    free_text: str | None = None,
    complete: bool = False,
    now: datetime | None = None,
) -> BetaSurvey | None:
    now = now or _utcnow()
    survey = await session.scalar(
        select(BetaSurvey).where(
            BetaSurvey.user_id == user_id,
            BetaSurvey.survey_key == SURVEY_KEY_A,
        )
    )
    if survey is None:
        return None
    if survey.status == "completed":
        return survey
    if result is not None:
        survey.result = clip_text(result, 32)
    if clarity_score is not None and 1 <= int(clarity_score) <= 5:
        survey.clarity_score = int(clarity_score)
    if free_text is not None:
        survey.free_text = clip_text(free_text, MAX_TEXT)
    if complete:
        survey.status = "completed"
        survey.completed_at = now
    return survey


async def count_bugs_today(
    session: AsyncSession, *, user_id: int, now: datetime | None = None
) -> int:
    now = now or _utcnow()
    start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    return int(
        await session.scalar(
            select(func.count())
            .select_from(BetaBug)
            .where(BetaBug.user_id == user_id, BetaBug.created_at >= start)
        )
        or 0
    )


async def create_bug(
    session: AsyncSession,
    *,
    user_id: int,
    severity: str,
    device_class: str,
    device_note: str | None,
    what_did: str,
    what_happened: str,
    what_expected: str,
    now: datetime | None = None,
) -> BetaBug | None:
    now = now or _utcnow()
    if await count_bugs_today(session, user_id=user_id, now=now) >= MAX_BUGS_PER_DAY:
        return None
    bug = BetaBug(
        user_id=user_id,
        severity=severity,
        device_class=device_class,
        device_note=clip_text(device_note, MAX_DEVICE_NOTE) or None,
        what_did=clip_text(what_did),
        what_happened=clip_text(what_happened),
        what_expected=clip_text(what_expected),
        created_at=now,
        status="open",
    )
    session.add(bug)
    await session.flush()
    return bug


async def beta_status_snapshot(session: AsyncSession) -> dict:
    paused = await is_beta_paused(session)
    participants = int(
        await session.scalar(select(func.count()).select_from(BetaParticipant)) or 0
    )
    active = int(
        await session.scalar(
            select(func.count())
            .select_from(BetaParticipant)
            .where(BetaParticipant.status == "active")
        )
        or 0
    )
    surveys_done = int(
        await session.scalar(
            select(func.count())
            .select_from(BetaSurvey)
            .where(BetaSurvey.status == "completed")
        )
        or 0
    )
    bugs_open = int(
        await session.scalar(
            select(func.count()).select_from(BetaBug).where(BetaBug.status == "open")
        )
        or 0
    )
    pending_jobs = int(
        await session.scalar(
            select(func.count()).select_from(BetaJob).where(BetaJob.status == "pending")
        )
        or 0
    )
    return {
        "paused": paused,
        "participants": participants,
        "active": active,
        "surveys_completed": surveys_done,
        "bugs_open": bugs_open,
        "pending_jobs": pending_jobs,
    }


async def list_recent_feedback(session: AsyncSession, *, limit: int = 10) -> list[BetaSurvey]:
    rows = await session.execute(
        select(BetaSurvey)
        .where(BetaSurvey.status == "completed")
        .order_by(BetaSurvey.completed_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def list_open_bugs(session: AsyncSession, *, limit: int = 20) -> list[BetaBug]:
    rows = await session.execute(
        select(BetaBug)
        .where(BetaBug.status == "open")
        .order_by(BetaBug.created_at.desc())
        .limit(limit)
    )
    return list(rows.scalars().all())


async def get_user_telegram_id(session: AsyncSession, *, user_id: int) -> int | None:
    user = await session.get(User, user_id)
    return int(user.telegram_id) if user else None
