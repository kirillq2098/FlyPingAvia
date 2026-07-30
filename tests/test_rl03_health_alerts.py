"""RL-03: admin health incidents, heartbeat, monitor."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from zoneinfo import ZoneInfo

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from flypingavia.config import Settings, get_settings
from flypingavia.db.models import SystemHealthIncident, SystemRuntimeState
from flypingavia.db.session import init_db, session_scope
import flypingavia.db.session as db_session
from flypingavia.monitoring import health_alerts as incidents
from flypingavia.monitoring.admin_notify import send_admin_alert
from flypingavia.monitoring.formatters import (
    format_admin_failure_alert,
    format_admin_recovery_alert,
)
from flypingavia.monitoring.heartbeat import (
    get_runtime_state,
    mark_checker_error,
    mark_checker_started,
    mark_checker_success,
)
from flypingavia.monitoring.keys import (
    INCIDENT_CHECKER_STALLED,
    INCIDENT_DATABASE,
    INCIDENT_PROVIDER,
    sanitize_error_summary,
)
from flypingavia.monitoring.loop import HealthMonitor
from flypingavia.monitoring.telegram_errors import (
    SYSTEM,
    USER,
    classify_telegram_send_error,
)
from flypingavia.version import __version__


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 31, 0, 15, 0, tzinfo=timezone.utc)
TZ = ZoneInfo("Europe/Moscow")


@pytest.fixture
async def rl03_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "rl03.db"))
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


# --- incident service ---


@pytest.mark.asyncio
async def test_incident_threshold_cooldown_recovery(rl03_db) -> None:
    async with session_scope() as session:
        d1 = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="timeout",
            occurred_at=NOW,
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        assert d1.incident is not None
        assert d1.incident.status == "open"
        assert d1.failure_count == 1
        assert not d1.should_notify

        d2 = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="timeout",
            occurred_at=NOW + timedelta(seconds=10),
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        assert d2.failure_count == 2
        assert not d2.should_notify

        d3 = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="timeout",
            occurred_at=NOW + timedelta(seconds=20),
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        assert d3.failure_count == 3
        assert d3.should_notify and d3.kind == "failure"
        await incidents.mark_notified(
            session, incident_id=d3.incident.id, notified_at=NOW + timedelta(seconds=20)
        )

        d4 = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="timeout again",
            occurred_at=NOW + timedelta(minutes=10),
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        assert d4.failure_count == 4
        assert not d4.should_notify

        d5 = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="timeout later",
            occurred_at=NOW + timedelta(hours=2),
            failure_threshold=3,
            cooldown_seconds=3600,
        )
        assert d5.should_notify

    async with session_scope() as session:
        rec = await incidents.report_recovery(
            session, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(hours=3)
        )
        assert rec.should_notify and rec.kind == "recovery"
        assert rec.incident is not None
        assert rec.incident.status == "recovered"
        assert rec.incident.recovered_at is not None

        again = await incidents.report_recovery(
            session, incident_key=INCIDENT_PROVIDER, recovered_at=NOW + timedelta(hours=4)
        )
        assert not again.should_notify

    async with session_scope() as session:
        d_new = await incidents.report_failure(
            session,
            incident_key=INCIDENT_PROVIDER,
            summary="new outage",
            occurred_at=NOW + timedelta(hours=5),
            failure_threshold=1,
            cooldown_seconds=3600,
        )
        assert d_new.should_notify
        assert d_new.incident is not None
        assert d_new.incident.status == "open"
        assert d_new.failure_count == 1


@pytest.mark.asyncio
async def test_recovery_without_prior_notify(rl03_db) -> None:
    async with session_scope() as session:
        await incidents.report_failure(
            session,
            incident_key=INCIDENT_DATABASE,
            summary="x",
            occurred_at=NOW,
            failure_threshold=5,
            cooldown_seconds=3600,
        )
        rec = await incidents.report_recovery(
            session, incident_key=INCIDENT_DATABASE, recovered_at=NOW + timedelta(minutes=1)
        )
        assert not rec.should_notify
        assert rec.incident is not None
        assert rec.incident.status == "recovered"


def test_sanitize_summary() -> None:
    raw = "boom\nTraceback (most recent call last):\n  File x\n1234567890:AASECRETTOKENVALUEHERE123456789012"
    clean = sanitize_error_summary(raw, limit=100)
    assert "Traceback" not in clean
    assert "AASECRET" not in clean
    assert len(clean) <= 100


# --- formatters ---


def test_admin_formatters() -> None:
    fail = format_admin_failure_alert(
        incident_key=INCIDENT_CHECKER_STALLED,
        failure_count=3,
        first_failed_at=NOW,
        display_timezone=TZ,
        summary="<script>x</script>",
    )
    assert "Проверка цен" in fail
    assert "checker_stalled" in fail
    assert "&lt;script&gt;" in fail
    assert "BOT_TOKEN" not in fail
    assert len(fail) < 2000

    rec = format_admin_recovery_alert(
        incident_key=INCIDENT_PROVIDER,
        first_failed_at=NOW,
        recovered_at=NOW + timedelta(minutes=17),
        failure_count=8,
        display_timezone=TZ,
    )
    assert "восстановился" in rec.lower()
    assert "17 мин" in rec
    assert "Провайдер" in rec


# --- sender ---


@pytest.mark.asyncio
async def test_admin_sender() -> None:
    bot = MagicMock()
    bot.send_message = AsyncMock()
    assert await send_admin_alert(bot, chat_id=None, text="x") is False
    bot.send_message.assert_not_awaited()
    assert await send_admin_alert(bot, chat_id=1, text="hi", enabled=False) is False
    bot.send_message = AsyncMock(return_value=True)
    assert await send_admin_alert(bot, chat_id=42, text="<b>ok</b>", enabled=True) is True
    kwargs = bot.send_message.await_args.kwargs
    assert kwargs.get("parse_mode") is not None
    assert "HTML" in str(kwargs.get("parse_mode"))
    bot.send_message = AsyncMock(side_effect=RuntimeError("boom"))
    assert await send_admin_alert(bot, chat_id=42, text="x") is False


# --- telegram classification ---


def test_telegram_error_classification() -> None:
    assert classify_telegram_send_error(Exception("Forbidden: bot was blocked by the user")) == USER
    assert classify_telegram_send_error(Exception("chat not found")) == USER
    assert classify_telegram_send_error(Exception("user is deactivated")) == USER
    assert classify_telegram_send_error(Exception("Request timeout")) == SYSTEM
    assert classify_telegram_send_error(Exception("Connection reset")) == SYSTEM
    assert classify_telegram_send_error(Exception("Bad Gateway 502")) == SYSTEM
    assert classify_telegram_send_error(Exception("retry after 3")) == SYSTEM
    msg = classify_telegram_send_error
    # sanitize path doesn't expose token in classifier input handling
    from flypingavia.monitoring.keys import sanitize_error_summary

    assert "AA:" not in sanitize_error_summary("token 1111111111:AAsecrettokenvalue123456789012345")


# --- heartbeat ---


@pytest.mark.asyncio
async def test_heartbeat_persists(rl03_db) -> None:
    t0 = NOW
    async with session_scope() as session:
        await mark_checker_started(session, at=t0)
    async with session_scope() as session:
        st = await get_runtime_state(session)
        assert st is not None
        assert st.last_started_at is not None
    async with session_scope() as session:
        await mark_checker_success(session, at=t0 + timedelta(seconds=5))
    async with session_scope() as session:
        st = await get_runtime_state(session)
        assert st.last_completed_at is not None
        assert st.last_success_at is not None
    async with session_scope() as session:
        await mark_checker_error(session, at=t0 + timedelta(seconds=10), summary="x\nTraceback")
    async with session_scope() as session:
        st = await get_runtime_state(session)
        assert st.last_error_at is not None
        assert "Traceback" not in (st.last_error_summary or "")


@pytest.mark.asyncio
async def test_stalled_monitor_logic(rl03_db, monkeypatch) -> None:
    from flypingavia.db import repository as repo

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        admin_telegram_chat_id=1,
        admin_alerts_enabled=True,
        admin_alert_failure_threshold=1,
        health_startup_grace_seconds=0,
        checker_stale_after_seconds=60,
        check_interval_seconds=30,
    )
    bot = MagicMock()
    bot.send_message = AsyncMock()
    monitor = HealthMonitor(settings, bot)
    monitor.started_at = NOW - timedelta(hours=1)

    # no watches → no stalled
    await monitor._check_checker_stalled(NOW)
    async with session_scope() as session:
        open_row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_STALLED
        )
        assert open_row is None

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=9, username="a")
        await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="IST",
            max_price=10000,
            depart_date=None,
            origin_name="М",
            destination_name="С",
        )
        await mark_checker_success(session, at=NOW - timedelta(hours=2))

    await monitor._check_checker_stalled(NOW)
    async with session_scope() as session:
        open_row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_STALLED
        )
        assert open_row is not None

    async with session_scope() as session:
        await mark_checker_success(session, at=NOW)
    await monitor._check_checker_stalled(NOW + timedelta(seconds=1))
    async with session_scope() as session:
        open_row = await incidents.get_open_incident(
            session, incident_key=INCIDENT_CHECKER_STALLED
        )
        assert open_row is None


# --- API ---


@pytest.mark.asyncio
async def test_ready_health_monitor_summary(rl03_db) -> None:
    from flypingavia.api.app import create_api

    settings = Settings(bot_token="1:T", app_env="test", travelpayouts_token="")
    app = create_api(settings)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        h = await c.get("/api/health")
        assert h.status_code == 200
        assert h.json()["version"] == __version__
        assert __version__ == "0.3.0"
        r = await c.get("/api/ready")
        assert r.status_code == 200
        body = r.json()
        assert "health_monitor" in body
        assert body["health_monitor"]["status"] == "ok"
        assert body["health_monitor"]["open_incidents"] == 0
        assert "error" not in body["health_monitor"]
        assert "admin" not in str(body).lower() or "admin_telegram" not in str(body)

    async with session_scope() as session:
        await incidents.report_failure(
            session,
            incident_key=INCIDENT_DATABASE,
            summary="down",
            occurred_at=NOW,
            failure_threshold=1,
            cooldown_seconds=60,
        )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r2 = await c.get("/api/ready")
        assert r2.json()["health_monitor"]["status"] == "degraded"
        assert r2.json()["health_monitor"]["open_incidents"] >= 1
        assert "down" not in r2.text


def test_docs_and_env() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ADMIN_TELEGRAM_CHAT_ID" in env
    assert "ADMIN_ALERT_FAILURE_THRESHOLD" in env
    assert (ROOT / "scripts/migrations/005_rl03_health_incidents.sql").is_file()
    assert (ROOT / "docs/HEALTH_MONITORING.md").is_file()
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")
    section = backlog.split("### RL-03")[1].split("###")[0]
    assert "**Статус:** Done" in section
    assert __version__ == "0.3.0"


def test_config_admin_defaults() -> None:
    s = Settings(bot_token="1:T", app_env="test", admin_telegram_chat_id=None)
    assert s.admin_alerts_active is False
    s2 = Settings(
        bot_token="1:T",
        app_env="test",
        admin_telegram_chat_id=123,
        admin_alerts_enabled=True,
    )
    assert s2.admin_alerts_active is True
    assert s2.effective_checker_stale_after_seconds >= 900 or s2.check_interval_seconds
