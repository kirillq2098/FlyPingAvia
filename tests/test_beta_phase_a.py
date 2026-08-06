"""Closed Beta Phase A — targeted tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from flypingavia.bot.beta_codes import is_allowed_beta_code, parse_beta_invite_code
from flypingavia.config import Settings
from flypingavia.db.models import BetaJob, BetaParticipant, BetaSurvey, User
from flypingavia.db.session import get_session_factory, init_db
from flypingavia.services import beta_repo as beta


@pytest.fixture
async def db(monkeypatch, tmp_path):
    db_path = tmp_path / "beta.db"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WEBAPP_URL", "")
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_SECRET", "x" * 32)
    # reset engine
    import flypingavia.db.session as sess

    sess._engine = None
    sess._session_factory = None
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    await init_db()
    yield
    get_settings.cache_clear()
    sess._engine = None
    sess._session_factory = None


async def _user(session, tg_id: int = 1001) -> User:
    from flypingavia.db import repository as repo

    return await repo.get_or_create_user(session, telegram_id=tg_id, username="t")


def test_parse_beta_invite_code():
    assert parse_beta_invite_code("beta_w1") == "w1"
    assert parse_beta_invite_code("beta_W1") == "w1"
    assert parse_beta_invite_code("share_abc") is None
    assert parse_beta_invite_code(None) is None
    assert is_allowed_beta_code("w1", allowed={"w1"})
    assert not is_allowed_beta_code("w2", allowed={"w1"})


@pytest.mark.asyncio
async def test_valid_beta_creates_participant(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        part, created = await beta.upsert_participant(
            session, user_id=user.id, cohort_code="w1"
        )
        await session.commit()
        assert created is True
        assert part.cohort_code == "w1"
        assert part.joined_at is not None


@pytest.mark.asyncio
async def test_invalid_code_helper():
    assert not is_allowed_beta_code("nope", allowed={"w1"})


@pytest.mark.asyncio
async def test_repeat_start_idempotent(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await session.commit()
    async with factory() as session:
        user = await _user(session)
        part, created = await beta.upsert_participant(
            session, user_id=user.id, cohort_code="w1"
        )
        await session.commit()
        assert created is False
        n = await session.scalar(select(BetaParticipant))
        assert n is not None


@pytest.mark.asyncio
async def test_onboarding_sent_once(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.mark_onboarding_sent(session, user_id=user.id)
        await session.commit()
    async with factory() as session:
        part = await beta.get_participant(session, user_id=1)
        # user id may not be 1 — reload
        user = await _user(session)
        part = await beta.get_participant(session, user_id=user.id)
        assert part is not None and part.onboarding_sent_at is not None
        before = part.onboarding_sent_at
        await beta.mark_onboarding_sent(session, user_id=user.id)
        await session.commit()
        part2 = await beta.get_participant(session, user_id=user.id)
        assert part2 is not None
        assert part2.onboarding_sent_at == before


@pytest.mark.asyncio
async def test_consent_and_opt_out_blocks_survey(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.set_consent(session, user_id=user.id)
        ok = await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=30)
        assert ok is True
        await beta.set_opt_out(session, user_id=user.id)
        ok2 = await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=30)
        assert ok2 is False
        jobs = (
            await session.execute(select(BetaJob).where(BetaJob.user_id == user.id))
        ).scalars().all()
        assert all(j.status == "cancelled" for j in jobs)
        await session.commit()


@pytest.mark.asyncio
async def test_first_watch_schedules_one_survey_job(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.set_consent(session, user_id=user.id)
        assert await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=60)
        assert not await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=60)
        surveys = (
            await session.execute(select(BetaSurvey).where(BetaSurvey.user_id == user.id))
        ).scalars().all()
        jobs = (
            await session.execute(select(BetaJob).where(BetaJob.user_id == user.id))
        ).scalars().all()
        assert len(surveys) == 1
        assert len(jobs) == 1
        assert jobs[0].logical_key == f"survey_a:{user.id}"
        await session.commit()


@pytest.mark.asyncio
async def test_job_survives_restart_claim(db):
    factory = get_session_factory()
    now = datetime.now(timezone.utc)
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.set_consent(session, user_id=user.id)
        await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=30)
        job = (await session.execute(select(BetaJob))).scalar_one()
        job.run_at = now - timedelta(seconds=1)
        await session.commit()
    async with factory() as session:
        claimed = await beta.claim_due_jobs(session, now=now)
        assert len(claimed) == 1
        assert claimed[0].status == "processing"
        await session.commit()
    async with factory() as session:
        claimed2 = await beta.claim_due_jobs(session, now=now)
        assert claimed2 == []
        await session.commit()


@pytest.mark.asyncio
async def test_dispatcher_does_not_call_price_provider(db, monkeypatch):
    from flypingavia.services import beta_dispatcher

    called = {"price": False}

    def boom(*a, **k):
        called["price"] = True
        raise AssertionError("price provider must not be called")

    monkeypatch.setattr(
        "flypingavia.services.prices.build_price_provider", boom, raising=False
    )
    settings = Settings(
        app_env="test",
        bot_token="1:x",
        beta_enabled=True,
        beta_invite_codes="w1",
        database_url="sqlite+aiosqlite:///:memory:",
    )
    # Use real DB from fixture via env already
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("BETA_ENABLED", "true")
    monkeypatch.setenv("BETA_INVITE_CODES", "w1")
    get_settings.cache_clear()
    settings = get_settings()

    bot = AsyncMock()
    bot.send_message = AsyncMock()
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session, tg_id=777)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.set_consent(session, user_id=user.id)
        await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=30)
        job = (await session.execute(select(BetaJob))).scalar_one()
        job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await session.commit()

    await beta_dispatcher.run_beta_dispatcher(bot=bot, settings=settings)
    assert called["price"] is False
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_double_callback_survey_complete_once(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.set_consent(session, user_id=user.id)
        await beta.schedule_survey_a(session, user_id=user.id, delay_seconds=30)
        await beta.apply_survey_result(
            session, user_id=user.id, result="yes", clarity_score=5, complete=True
        )
        s2 = await beta.apply_survey_result(
            session, user_id=user.id, result="no", complete=True
        )
        assert s2 is not None
        assert s2.result == "yes"
        await session.commit()


@pytest.mark.asyncio
async def test_bug_create_and_daily_limit(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        for i in range(3):
            bug = await beta.create_bug(
                session,
                user_id=user.id,
                severity="P2",
                device_class="android",
                device_note=None,
                what_did=f"did{i}",
                what_happened="happened",
                what_expected="expected",
            )
            assert bug is not None
        fourth = await beta.create_bug(
            session,
            user_id=user.id,
            severity="P1",
            device_class="iphone",
            device_note=None,
            what_did="did",
            what_happened="happened",
            what_expected="expected",
        )
        assert fourth is None
        await session.commit()


@pytest.mark.asyncio
async def test_telegram_forbidden_marks_blocked(db):
    factory = get_session_factory()
    async with factory() as session:
        user = await _user(session)
        await beta.upsert_participant(session, user_id=user.id, cohort_code="w1")
        await beta.mark_participant_blocked(session, user_id=user.id)
        part = await beta.get_participant(session, user_id=user.id)
        assert part is not None
        assert part.status == "blocked"
        assert not beta.messaging_allowed(part)
        await session.commit()


def test_admin_gate_empty_rejects():
    s = Settings(
        app_env="test",
        bot_token="1:x",
        admin_telegram_user_ids="",
        admin_telegram_chat_id=None,
    )
    assert 42 not in s.admin_user_id_set


def test_admin_gate_allows_listed():
    s = Settings(
        app_env="test",
        bot_token="1:x",
        admin_telegram_user_ids="42,43",
        admin_telegram_chat_id=None,
    )
    assert 42 in s.admin_user_id_set
    assert 99 not in s.admin_user_id_set
