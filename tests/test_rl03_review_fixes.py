"""RL-03 review fixes: DB outage fallback, checker_crashed, recovery delivery."""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from flypingavia.config import Settings, get_settings
from flypingavia.db.models import SystemHealthIncident, SystemRuntimeState
from flypingavia.db.session import init_db, session_scope
import flypingavia.db.session as db_session
from flypingavia.monitoring import health_alerts as incidents
from flypingavia.monitoring.checker_job import run_checker_job
from flypingavia.monitoring.db_fallback import DatabaseOutageTracker
from flypingavia.monitoring.keys import (
    COMPONENT_PRICE_CHECKER,
    INCIDENT_CHECKER_CRASHED,
    INCIDENT_DATABASE,
    INCIDENT_PROVIDER,
)
from flypingavia.monitoring.loop import HealthMonitor
from flypingavia.monitoring.notify import notify_recovery, retry_pending_recoveries


NOW = datetime(2026, 7, 31, 1, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def rl03_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "rl03_fix.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None
    await init_db()
    yield
    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


def _settings(**kwargs) -> Settings:
    base = dict(
        bot_token="1:T",
        app_env="test",
        admin_telegram_chat_id=42,
        admin_alerts_enabled=True,
        admin_alert_failure_threshold=3,
        admin_alert_cooldown_seconds=3600,
        health_startup_grace_seconds=0,
    )
    base.update(kwargs)
    return Settings(**base)


# --- DB outage fallback ---


@pytest.mark.asyncio
async def test_db_outage_no_secondary_db_write(rl03_db) -> None:
    tracker = DatabaseOutageTracker()
    bot = MagicMock()
    bot.send_message = AsyncMock()
    settings = _settings(admin_alert_failure_threshold=1)

    with patch(
        "flypingavia.db.session.session_scope",
        side_effect=AssertionError("DB must not be used during outage notify"),
    ):
        await tracker.report_failure(
            bot, settings, summary="OperationalError", occurred_at=NOW
        )
    assert tracker.state.failure_notification_sent is True
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_db_outage_threshold_cooldown_and_retry(rl03_db) -> None:
    tracker = DatabaseOutageTracker()
    bot = MagicMock()
    bot.send_message = AsyncMock()
    settings = _settings(admin_alert_failure_threshold=3, admin_alert_cooldown_seconds=3600)

    await tracker.report_failure(bot, settings, summary="Timeout", occurred_at=NOW)
    assert tracker.state.failure_count == 1
    bot.send_message.assert_not_awaited()

    await tracker.report_failure(
        bot, settings, summary="Timeout", occurred_at=NOW + timedelta(seconds=1)
    )
    assert tracker.state.failure_count == 2
    bot.send_message.assert_not_awaited()

    await tracker.report_failure(
        bot, settings, summary="Timeout", occurred_at=NOW + timedelta(seconds=2)
    )
    assert tracker.state.failure_count == 3
    assert tracker.state.failure_notification_sent is True
    assert tracker.state.last_notified_at is not None
    bot.send_message.assert_awaited()

    bot.send_message.reset_mock()
    await tracker.report_failure(
        bot, settings, summary="Timeout", occurred_at=NOW + timedelta(minutes=10)
    )
    bot.send_message.assert_not_awaited()

    await tracker.report_failure(
        bot, settings, summary="Timeout", occurred_at=NOW + timedelta(hours=2)
    )
    bot.send_message.assert_awaited()


@pytest.mark.asyncio
async def test_db_outage_failed_send_not_marked(rl03_db) -> None:
    tracker = DatabaseOutageTracker()
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("tg down"))
    settings = _settings(admin_alert_failure_threshold=1)

    await tracker.report_failure(bot, settings, summary="Err", occurred_at=NOW)
    assert tracker.state.failure_notification_sent is False
    assert tracker.state.last_notified_at is None

    bot.send_message = AsyncMock()
    await tracker.report_failure(
        bot, settings, summary="Err", occurred_at=NOW + timedelta(seconds=1)
    )
    assert tracker.state.failure_notification_sent is True


@pytest.mark.asyncio
async def test_db_outage_recovery_paths(rl03_db) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    # без prior failure alert — без recovery send
    t1 = DatabaseOutageTracker()
    settings_hi = _settings(admin_alert_failure_threshold=5)
    await t1.report_failure(bot, settings_hi, summary="x", occurred_at=NOW)
    bot.send_message.reset_mock()
    await t1.report_recovery(bot, settings_hi, recovered_at=NOW + timedelta(minutes=1))
    bot.send_message.assert_not_awaited()
    assert not t1.has_outage()
    async with session_scope() as session:
        rows = list(
            (
                await session.execute(
                    select(SystemHealthIncident).where(
                        SystemHealthIncident.incident_key == INCIDENT_DATABASE
                    )
                )
            ).scalars()
        )
        assert len(rows) == 1
        assert rows[0].status == "recovered"

    # после delivered failure — recovery; failed send → retry; success → clear + sync
    t2 = DatabaseOutageTracker()
    await t2.report_failure(bot, settings, summary="Boom", occurred_at=NOW)
    assert t2.state.failure_notification_sent
    bot.send_message = AsyncMock(side_effect=RuntimeError("fail"))
    await t2.report_recovery(bot, settings, recovered_at=NOW + timedelta(minutes=2))
    assert t2.state.recovery_pending is True
    assert t2.has_outage()

    bot.send_message = AsyncMock()
    await t2.report_recovery(bot, settings, recovered_at=NOW + timedelta(minutes=3))
    assert not t2.has_outage()
    text = bot.send_message.await_args.kwargs["text"]
    assert "восстанов" in text.lower() or "recover" in text.lower() or "База" in text
    assert "postgresql://" not in text.lower()
    assert "sqlite:" not in text.lower()


@pytest.mark.asyncio
async def test_db_failure_does_not_block_other_checks(rl03_db, monkeypatch) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    tracker = DatabaseOutageTracker()
    monitor = HealthMonitor(settings, bot, database_outage=tracker)

    calls: list[str] = []

    async def boom(_now: datetime) -> None:
        calls.append("database")
        raise RuntimeError("db down")

    async def ok_checker(_now: datetime) -> None:
        calls.append("checker")

    async def ok_ready(_now: datetime) -> None:
        calls.append("readiness")

    async def ok_web(_now: datetime) -> None:
        calls.append("webapp")

    monkeypatch.setattr(monitor, "_check_database", boom)
    monkeypatch.setattr(monitor, "_check_checker_stalled", ok_checker)
    monkeypatch.setattr(monitor, "_check_readiness", ok_ready)
    monkeypatch.setattr(monitor, "_check_webapp", ok_web)
    monkeypatch.setattr(monitor, "_retry_pending_recoveries", AsyncMock())

    await monitor.run_once()
    assert calls == ["database", "checker", "readiness", "webapp"]


@pytest.mark.asyncio
async def test_db_check_uses_fallback_not_notify_failure(rl03_db) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    tracker = DatabaseOutageTracker()
    monitor = HealthMonitor(settings, bot, database_outage=tracker)

    with (
        patch(
            "flypingavia.monitoring.loop.session_scope",
            side_effect=RuntimeError("connection refused postgresql://secret@host/db"),
        ),
        patch("flypingavia.monitoring.loop.notify_failure", new_callable=AsyncMock) as nf,
    ):
        await monitor._check_database(NOW)

    nf.assert_not_awaited()
    assert tracker.state.failure_count == 1
    # summary — только тип, без URL
    assert "postgresql" not in tracker.state.last_error_summary.lower()
    assert "secret" not in tracker.state.last_error_summary.lower()


# --- checker_crashed ---


@pytest.mark.asyncio
async def test_checker_job_success_and_crash(rl03_db) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    checker = MagicMock()
    checker.run_once = AsyncMock(return_value=7)
    assert await run_checker_job(checker, bot, settings) == 7

    async with session_scope() as session:
        open_crash = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_CRASHED
        )
        assert open_crash is None

    checker.run_once = AsyncMock(side_effect=RuntimeError("unexpected boom"))
    assert await run_checker_job(checker, bot, settings) == 0

    async with session_scope() as session:
        row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_CRASHED
        )
        assert row is not None
        assert row.last_error_summary == "RuntimeError"
        assert "boom" not in (row.last_error_summary or "")
        assert "Traceback" not in (row.last_error_summary or "")
        hb = await session.get(SystemRuntimeState, COMPONENT_PRICE_CHECKER)
        assert hb is not None
        assert hb.last_error_at is not None
        assert hb.last_error_summary == "RuntimeError"

    checker.run_once = AsyncMock(return_value=1)
    assert await run_checker_job(checker, bot, settings) == 1
    async with session_scope() as session:
        # recovery pending or recovered after successful send
        open_row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_CRASHED
        )
        # send succeeded → recovered (not in ACTIVE)
        assert open_row is None
        all_rows = list(
            (
                await session.execute(
                    select(SystemHealthIncident).where(
                        SystemHealthIncident.incident_key == INCIDENT_CHECKER_CRASHED
                    )
                )
            ).scalars()
        )
        assert any(r.status == "recovered" for r in all_rows)


@pytest.mark.asyncio
async def test_checker_job_cancelled_propagates(rl03_db) -> None:
    settings = _settings()
    bot = MagicMock()
    checker = MagicMock()
    checker.run_once = AsyncMock(side_effect=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await run_checker_job(checker, bot, settings)


@pytest.mark.asyncio
async def test_provider_failure_inside_checker_not_crashed(rl03_db) -> None:
    """Штатный provider path внутри checker не должен вызывать wrapper crash."""
    from flypingavia.services.checker import PriceChecker

    src = inspect.getsource(PriceChecker._run_once_locked)
    assert "INCIDENT_PROVIDER" in src
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()
    checker = MagicMock()
    # run_once сам обработал provider error и вернул код без exception
    checker.run_once = AsyncMock(return_value=0)
    assert await run_checker_job(checker, bot, settings) == 0
    async with session_scope() as session:
        assert (
            await incidents.get_open_incident(
                session, incident_key=INCIDENT_CHECKER_CRASHED
            )
            is None
        )


def test_scheduler_uses_wrapper() -> None:
    import flypingavia.main as main_mod

    src = inspect.getsource(main_mod._async_main)
    assert "run_checker_job" in src
    assert "checker.run_once," not in src.replace(" ", "")


# --- recovery delivery ---


@pytest.mark.asyncio
async def test_recovery_pending_delivery_and_restart(rl03_db) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    async with session_scope() as session:
        d = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="x",
            occurred_at=NOW,
            failure_threshold=1,
            cooldown_seconds=3600,
        )
        await incidents.mark_notified(
            session, incident_id=d.incident.id, notified_at=NOW
        )

    async with session_scope() as session:
        pending = await incidents.detect_recovery(
            session, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(minutes=5)
        )
        assert pending.should_notify
        assert pending.incident.status == "recovery_pending"
        incident_id = pending.incident.id
        first = pending.incident.first_failed_at

    # ошибка отправки — pending сохраняется
    bot.send_message = AsyncMock(side_effect=RuntimeError("tg"))
    await notify_recovery(
        bot, settings, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(minutes=6)
    )
    async with session_scope() as session:
        row = await session.get(SystemHealthIncident, incident_id)
        assert row.status == "recovery_pending"
        assert row.recovery_notified_at is None

    # новая session = имитация restart: retry
    bot.send_message = AsyncMock()
    await retry_pending_recoveries(bot, settings)
    async with session_scope() as session:
        row = await session.get(SystemHealthIncident, incident_id)
        assert row.status == "recovered"
        assert row.recovery_notified_at is not None
        assert row.first_failed_at == first

    # повтор не шлёт duplicate
    bot.send_message.reset_mock()
    await retry_pending_recoveries(bot, settings)
    await notify_recovery(
        bot, settings, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(hours=1)
    )
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_recovery_without_failure_alert_closes_quietly(rl03_db) -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    settings = _settings(admin_alert_failure_threshold=5)

    async with session_scope() as session:
        await incidents.report_failure(
            session,
            incident_key=INCIDENT_DATABASE,
            summary="x",
            occurred_at=NOW,
            failure_threshold=5,
            cooldown_seconds=3600,
        )

    await notify_recovery(
        bot, settings, incident_key=INCIDENT_DATABASE, recovered_at=NOW + timedelta(minutes=1)
    )
    bot.send_message.assert_not_awaited()
    async with session_scope() as session:
        open_row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_DATABASE
        )
        assert open_row is None


@pytest.mark.asyncio
async def test_failure_cooldown_does_not_block_recovery(rl03_db) -> None:
    settings = _settings(
        admin_alert_failure_threshold=1, admin_alert_cooldown_seconds=86400
    )
    bot = MagicMock()
    bot.send_message = AsyncMock()

    async with session_scope() as session:
        d = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="x",
            occurred_at=NOW,
            failure_threshold=1,
            cooldown_seconds=86400,
        )
        await incidents.mark_notified(session, incident_id=d.incident.id, notified_at=NOW)

    # сразу после failure notify — recovery всё равно должна уйти
    await notify_recovery(
        bot, settings, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(seconds=5)
    )
    bot.send_message.assert_awaited()
    text = bot.send_message.await_args.kwargs["text"]
    assert "5" in text or "сек" in text or "мин" in text


@pytest.mark.asyncio
async def test_duplicate_detect_recovery_does_not_finalize_twice(rl03_db) -> None:
    settings = _settings(admin_alert_failure_threshold=1)
    bot = MagicMock()
    bot.send_message = AsyncMock()

    async with session_scope() as session:
        d = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="x",
            occurred_at=NOW,
            failure_threshold=1,
            cooldown_seconds=60,
        )
        await incidents.mark_notified(session, incident_id=d.incident.id, notified_at=NOW)

    await notify_recovery(
        bot, settings, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(minutes=1)
    )
    assert bot.send_message.await_count == 1
    await notify_recovery(
        bot, settings, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(minutes=2)
    )
    assert bot.send_message.await_count == 1
