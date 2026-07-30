"""NT-04: anti-spam — cooldown and min price delta (integration with PriceChecker)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from flypingavia.db import repository as repo
from flypingavia.db.models import AlertEvent, Watch
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import PriceBand, PriceProvider, PriceQuote


class FixedPriceProvider(PriceProvider):
    """Controlled quotes for antispam tests (route → price)."""

    def __init__(self, prices: dict[tuple[str, str], float] | float) -> None:
        if isinstance(prices, (int, float)):
            self._default = float(prices)
            self._by_route: dict[tuple[str, str], float] = {}
        else:
            self._default = 10_000.0
            self._by_route = {
                (o.upper(), d.upper()): float(p) for (o, d), p in prices.items()
            }

    def set_price(self, origin: str, destination: str, price: float) -> None:
        self._by_route[(origin.upper(), destination.upper())] = float(price)

    def set_default(self, price: float) -> None:
        self._default = float(price)

    def _price_for(self, origins: Sequence[str], destinations: Sequence[str]) -> tuple[float, str, str]:
        for o in origins:
            for d in destinations:
                key = (o.upper(), d.upper())
                if key in self._by_route:
                    return self._by_route[key], o.upper(), d.upper()
        o = origins[0].upper() if origins else "XXX"
        d = destinations[0].upper() if destinations else "YYY"
        return self._default, o, d

    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        _ = depart_date
        price = self._by_route.get(
            (origin.upper(), destination.upper()),
            self._default,
        )
        return PriceQuote(
            price=price,
            currency=currency.upper(),
            airline="SU",
            transfers=0,
            source="test",
            origin_code=origin.upper(),
            destination_code=destination.upper(),
        )

    async def get_price_band(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        _ = depart_date
        price = self._by_route.get(
            (origin.upper(), destination.upper()),
            self._default,
        )
        return PriceBand(
            cheap_max=price * 0.9,
            typical=price,
            expensive_min=price * 1.2,
            sample_size=10,
            currency=currency.upper(),
            source="test",
        )

    async def get_trip_quote(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        *,
        depart_date: Optional[date] = None,
        return_date: Optional[date] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        _ = (depart_date, return_date)
        price, o, d = self._price_for(origins, destinations)
        return PriceQuote(
            price=price,
            currency=currency.upper(),
            airline="SU",
            transfers=0,
            source="test",
            origin_code=o,
            destination_code=d,
            adults=adults,
            children=children,
            infants=infants,
        )

    async def get_trip_band(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        *,
        depart_date: Optional[date] = None,
        return_date: Optional[date] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        _ = (depart_date, return_date, adults, children, infants)
        price, _, _ = self._price_for(origins, destinations)
        return PriceBand(
            cheap_max=price * 0.9,
            typical=price,
            expensive_min=price * 1.2,
            sample_size=10,
            currency=currency.upper(),
            source="test",
        )


@pytest_asyncio.fixture
async def isolated_checker_env(tmp_path, monkeypatch):
    """Fresh SQLite; override DB_PATH from .env so tests never touch prod data."""
    db_path = tmp_path / "nt04.db"
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


async def _seed_watch(
    *,
    telegram_id: int = 9001,
    origin: str = "MOW",
    destination: str = "LED",
    max_price: float = 20_000,
) -> Watch:
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=telegram_id)
        watch = await repo.add_watch(
            session,
            user=user,
            origin=origin,
            destination=destination,
            max_price=max_price,
            depart_date=date.today() + timedelta(days=30),
        )
        await session.flush()
        return watch


async def _add_alert(
    watch_id: int,
    user_id: int,
    price: float,
    *,
    hours_ago: float,
    threshold: float = 20_000,
) -> None:
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        await repo.log_alert_event(
            session,
            watch_id=watch_id,
            user_id=user_id,
            price=price,
            threshold=threshold,
            sent_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
        )
        fresh = await session.get(Watch, watch_id)
        if fresh is not None:
            fresh.last_alert_price = price


async def _event_count() -> int:
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        rows = (await session.execute(select(AlertEvent))).scalars().all()
        return len(rows)


@pytest.mark.asyncio
async def test_first_notification_sent(isolated_checker_env) -> None:
    settings = isolated_checker_env
    watch = await _seed_watch()
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(8_000)

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 1
    bot.send_message.assert_awaited()
    assert await _event_count() == 1

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        fresh = await session.get(Watch, watch.id)
        assert fresh is not None
        assert fresh.last_alert_price == 8_000


@pytest.mark.asyncio
async def test_cooldown_active_skips(isolated_checker_env) -> None:
    settings = isolated_checker_env
    watch = await _seed_watch()
    await _add_alert(watch.id, watch.user_id, 8_000, hours_ago=1)

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    # drop 100 < 500 inside cooldown
    provider = FixedPriceProvider(7_900)

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 0
    bot.send_message.assert_not_awaited()
    assert await _event_count() == 1


@pytest.mark.asyncio
async def test_cooldown_expired_allows(isolated_checker_env) -> None:
    settings = isolated_checker_env
    watch = await _seed_watch()
    await _add_alert(watch.id, watch.user_id, 8_000, hours_ago=25)

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(8_000)  # same price, cooldown done

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 1
    assert await _event_count() == 2


@pytest.mark.asyncio
async def test_price_delta_too_small_skips(isolated_checker_env) -> None:
    settings = isolated_checker_env
    watch = await _seed_watch()
    await _add_alert(watch.id, watch.user_id, 8_000, hours_ago=1)

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(7_600)  # drop 400 < 500

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 0
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_price_delta_significant_allows(isolated_checker_env) -> None:
    settings = isolated_checker_env
    watch = await _seed_watch()
    await _add_alert(watch.id, watch.user_id, 8_000, hours_ago=1)

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(7_400)  # drop 600 >= 500

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 1
    assert await _event_count() == 2

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        fresh = await session.get(Watch, watch.id)
        assert fresh is not None
        assert fresh.last_alert_price == 7_400


@pytest.mark.asyncio
async def test_watches_independent(isolated_checker_env) -> None:
    """Cooldown on watch A must not block watch B."""
    settings = isolated_checker_env
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=4242)
        w_a = await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="LED",
            max_price=20_000,
            depart_date=date.today() + timedelta(days=20),
        )
        w_b = await repo.add_watch(
            session,
            user=user,
            origin="SVO",
            destination="AER",
            max_price=20_000,
            depart_date=date.today() + timedelta(days=20),
        )
        await session.flush()
        a_id, b_id, uid = w_a.id, w_b.id, user.id

    await _add_alert(a_id, uid, 8_000, hours_ago=1)

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(
        {
            ("MOW", "LED"): 7_900,  # A: small drop under cooldown → skip
            ("SVO", "AER"): 12_000,  # B: first alert → send
        }
    )

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 1
    assert bot.send_message.await_count == 1

    async with session_scope() as session:
        events = (await session.execute(select(AlertEvent))).scalars().all()
        assert len(events) == 2  # A's old + B's new
        watch_ids = {e.watch_id for e in events}
        assert b_id in watch_ids
        assert a_id in watch_ids


@pytest.mark.asyncio
async def test_an03_no_regression_failed_send(isolated_checker_env) -> None:
    """Failed Telegram send must not create AlertEvent (AN-03)."""
    settings = isolated_checker_env
    watch = await _seed_watch()
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("telegram down"))
    provider = FixedPriceProvider(5_000)

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()

    assert sent == 0
    assert await _event_count() == 0

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        fresh = await session.get(Watch, watch.id)
        assert fresh is not None
        assert fresh.last_alert_price is None
