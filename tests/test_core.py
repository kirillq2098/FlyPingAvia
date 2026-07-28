from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.models import Base
from flypingavia.services.prices import DemoPriceProvider, build_affiliate_url


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
async def test_add_and_list_watch(session: AsyncSession) -> None:
    user = await repo.get_or_create_user(session, telegram_id=42, username="kirill")
    watch = await repo.add_watch(
        session,
        user=user,
        origin="mow",
        destination="ist",
        max_price=15000,
        depart_date=date.today() + timedelta(days=30),
    )
    await session.commit()

    watches = await repo.list_watches(session, user.id)
    assert len(watches) == 1
    assert watches[0].origin == "MOW"
    assert watches[0].id == watch.id


@pytest.mark.asyncio
async def test_deactivate_watch(session: AsyncSession) -> None:
    user = await repo.get_or_create_user(session, telegram_id=7)
    watch = await repo.add_watch(
        session,
        user=user,
        origin="MOW",
        destination="AYT",
        max_price=10000,
        depart_date=None,
    )
    await session.commit()

    ok = await repo.deactivate_watch(session, user.id, watch.id)
    await session.commit()
    assert ok is True
    assert await repo.count_active_watches(session, user.id) == 0


@pytest.mark.asyncio
async def test_demo_price_provider_stable() -> None:
    provider = DemoPriceProvider()
    a = await provider.get_cheapest("MOW", "IST", date(2026, 9, 1))
    b = await provider.get_cheapest("MOW", "IST", date(2026, 9, 1))
    assert a is not None and b is not None
    assert a.price == b.price
    assert a.source == "demo"


def test_affiliate_url_contains_marker() -> None:
    url = build_affiliate_url("MOW", "DXB", marker="flypingavia", depart_date=date(2026, 10, 1))
    assert "origin_iata=MOW" in url
    assert "destination_iata=DXB" in url
    assert "marker=flypingavia" in url
    assert "depart_date=2026-10-01" in url


def test_settings_demo_flag() -> None:
    s = Settings(bot_token="x", travelpayouts_token="")
    assert s.is_demo_prices is True
    s2 = Settings(bot_token="x", travelpayouts_token="tok")
    assert s2.is_demo_prices is False
