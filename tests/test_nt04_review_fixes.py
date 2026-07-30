"""NT-04 review fixes: run lock, split Telegram/DB errors, config validation."""

from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from pydantic import ValidationError
from sqlalchemy import select

from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.models import AlertEvent, Watch
from flypingavia.services.checker import PriceChecker
from tests.test_nt04_antispam import FixedPriceProvider


@pytest_asyncio.fixture
async def isolated_checker_env(tmp_path, monkeypatch):
    db_path = tmp_path / "nt04_review.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("NOTIFICATION_COOLDOWN_HOURS", "24")
    monkeypatch.setenv("MIN_PRICE_DELTA", "500")

    from flypingavia.config import get_settings
    import flypingavia.db.session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None

    from flypingavia.db.session import init_db

    await init_db()
    yield get_settings()

    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_concurrent_run_once_skipped(isolated_checker_env, caplog) -> None:
    """Second overlapping run_once must skip while the first holds the lock."""
    settings = isolated_checker_env
    bot = AsyncMock()
    provider = FixedPriceProvider(8_000)
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)

    started = asyncio.Event()
    release = asyncio.Event()

    async def _hold_lock() -> int:
        async with checker._run_lock:
            started.set()
            await release.wait()
            return 0

    holder = asyncio.create_task(_hold_lock())
    await started.wait()

    with caplog.at_level(logging.INFO, logger="flypingavia.services.checker"):
        skipped = await checker.run_once()

    assert skipped == 0
    assert "Price check skipped: another run is active" in caplog.text
    bot.send_message.assert_not_awaited()

    release.set()
    await holder


@pytest.mark.asyncio
async def test_persistence_failure_after_successful_send(
    isolated_checker_env,
    monkeypatch,
    caplog,
) -> None:
    """Telegram OK + DB fail → correct log, alert not counted as fully processed."""
    settings = isolated_checker_env
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=9101)
        await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="LED",
            max_price=20_000,
            depart_date=date.today() + timedelta(days=30),
        )

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(5_000)
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)

    async def _fail_log(*_args, **_kwargs):
        raise RuntimeError("db write failed")

    monkeypatch.setattr(repo, "log_alert_event", _fail_log)

    with caplog.at_level(logging.ERROR, logger="flypingavia.services.checker"):
        sent = await checker.run_once()

    assert sent == 0
    bot.send_message.assert_awaited()
    assert "Alert sent successfully but AlertEvent persistence failed" in caplog.text
    assert "Не удалось отправить алерт" not in caplog.text

    async with session_scope() as session:
        events = (await session.execute(select(AlertEvent))).scalars().all()
        assert len(events) == 0
        watch = (await session.execute(select(Watch))).scalar_one()
        assert watch.last_alert_price is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("notification_cooldown_hours", -1),
        ("min_price_delta", -500),
    ],
)
def test_antispam_config_rejects_negative(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value, "bot_token": "123:TEST"})


def test_antispam_config_accepts_zero() -> None:
    settings = Settings(
        bot_token="123:TEST",
        notification_cooldown_hours=0,
        min_price_delta=0,
    )
    assert settings.notification_cooldown_hours == 0
    assert settings.min_price_delta == 0
