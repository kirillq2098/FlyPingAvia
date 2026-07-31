from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flypingavia.db import repository as repo
from flypingavia.db.models import AlertEvent, Base
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import DemoPriceProvider


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        yield sess
    await engine.dispose()


@pytest.mark.asyncio
async def test_log_alert_event_and_count_watchers(session: AsyncSession) -> None:
    user = await repo.get_or_create_user(session, telegram_id=1001, username="u1")
    watch = await repo.add_watch(
        session,
        user=user,
        origin="MOW",
        destination="AYT",
        max_price=20000,
        depart_date=date.today() + timedelta(days=40),
    )
    await session.commit()

    event = await repo.log_alert_event(
        session,
        watch_id=watch.id,
        user_id=user.id,
        price=15000,
        threshold=20000,
        currency="RUB",
    )
    await session.commit()

    assert event.id is not None
    assert event.price == 15000
    assert event.threshold == 20000
    assert event.sent_at is not None

    rows = (await session.execute(select(AlertEvent))).scalars().all()
    assert len(rows) == 1
    assert await repo.count_alerted_watchers(session, within_days=30) == 1


@pytest.mark.asyncio
async def test_count_alerted_watchers_ignores_old_events(session: AsyncSession) -> None:
    user = await repo.get_or_create_user(session, telegram_id=1002)
    watch = await repo.add_watch(
        session,
        user=user,
        origin="LED",
        destination="AYT",
        max_price=18000,
        depart_date=None,
    )
    old = datetime.now(timezone.utc) - timedelta(days=45)
    await repo.log_alert_event(
        session,
        watch_id=watch.id,
        user_id=user.id,
        price=10000,
        threshold=18000,
        sent_at=old,
    )
    await session.commit()

    assert await repo.count_alerted_watchers(session, within_days=30) == 0


@pytest.mark.asyncio
async def test_checker_logs_alert_only_after_successful_send(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    db_path = tmp_path / "alerts.db"
    # DB_PATH из .env перекрывает DATABASE_URL в Settings — сбрасываем явно.
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")

    from flypingavia.config import get_settings
    import flypingavia.db.session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None

    from flypingavia.db.session import init_db, session_scope

    await init_db()

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=777001)
        await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="IST",
            max_price=999_999,
            depart_date=date.today() + timedelta(days=20),
        )

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    settings = get_settings()
    checker = PriceChecker(bot=bot, settings=settings, provider=DemoPriceProvider())

    sent = await checker.run_once()
    assert sent >= 1
    bot.send_message.assert_awaited()

    async with session_scope() as session:
        events = (await session.execute(select(AlertEvent))).scalars().all()
        assert len(events) >= 1
        assert events[0].threshold == 999_999
        assert await repo.count_alerted_watchers(session, within_days=30) == 1
        before = len(events)

    bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))
    await checker.run_once()

    async with session_scope() as session:
        events_after = (await session.execute(select(AlertEvent))).scalars().all()
        assert len(events_after) == before

    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()
