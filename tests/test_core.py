from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.models import Base
from flypingavia.services.locations import _norm, resolve_place
from flypingavia.services.prices import (
    DemoPriceProvider,
    PriceLevel,
    build_affiliate_url,
    compute_price_band,
    passenger_total,
)
from flypingavia.bot.formatters import format_band_block, format_price_card, money



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
    assert "one_way=true" in url
    assert "adults=1" in url


def test_affiliate_url_round_trip_and_passengers() -> None:
    url = build_affiliate_url(
        "MOW",
        "AYT",
        marker="flypingavia",
        depart_date=date(2026, 10, 1),
        return_date=date(2026, 10, 10),
        adults=2,
        children=1,
        infants=1,
    )
    assert "return_date=2026-10-10" in url
    assert "one_way=false" in url
    assert "adults=2" in url
    assert "children=1" in url
    assert "infants=1" in url


def test_passenger_total() -> None:
    # 2 взр + 1 реб (полный тариф) + 1 мл (10%) = 2+1+0.1
    assert passenger_total(10_000, adults=2, children=1, infants=1) == 31_000


@pytest.mark.asyncio
async def test_trip_quote_round_trip() -> None:
    provider = DemoPriceProvider()
    ow = await provider.get_trip_quote(["MOW"], ["AYT"], depart_date=date(2026, 9, 1), adults=1)
    rt = await provider.get_trip_quote(
        ["MOW"],
        ["AYT"],
        depart_date=date(2026, 9, 1),
        return_date=date(2026, 9, 10),
        adults=2,
        children=1,
    )
    assert ow is not None and rt is not None
    assert rt.return_date == date(2026, 9, 10)
    assert rt.adults == 2
    assert rt.children == 1
    # цена всегда за 1 взр.; RT дороже one-way, состав не умножает цену
    assert rt.price == rt.price_per_adult
    assert rt.price > ow.price
    assert rt.price == ow.price * 2 or rt.price > ow.price  # sum of legs or ×2 fallback


@pytest.mark.asyncio
async def test_add_watch_with_passengers(session: AsyncSession) -> None:
    user = await repo.get_or_create_user(session, telegram_id=99, username="pax")
    watch = await repo.add_watch(
        session,
        user=user,
        origin="MOW",
        destination="AYT",
        max_price=45000,
        depart_date=date(2026, 9, 1),
        return_date=date(2026, 9, 12),
        adults=2,
        children=1,
        infants=0,
    )
    await session.commit()
    assert watch.is_round_trip is True
    assert "дет. 1" in watch.passengers_label
    assert "туда-обратно" in watch.route_label


def test_settings_demo_flag() -> None:
    s = Settings(bot_token="x", travelpayouts_token="")
    assert s.is_demo_prices is True
    s2 = Settings(bot_token="x", travelpayouts_token="tok")
    assert s2.is_demo_prices is False


def test_settings_aliases_from_user_env(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_TOKEN", "111:AAA")
    monkeypatch.setenv("AVIASALES_API_TOKEN", "secret")
    monkeypatch.setenv("CHECK_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("DB_PATH", "data/avia_bot.sqlite3")
    monkeypatch.setenv("CURRENCY", "rub")
    # сбрасываем кэш не нужен — создаём Settings напрямую
    s = Settings(_env_file=None)
    assert s.bot_token == "111:AAA"
    assert s.travelpayouts_token == "secret"
    assert s.is_demo_prices is False
    assert s.poll_interval_seconds == 60
    assert "avia_bot.sqlite3" in s.database_url
    assert s.currency == "rub"


def test_compute_price_band_levels() -> None:
    band = compute_price_band([5000, 7000, 9000, 11000, 15000, 20000], currency="RUB")
    assert band is not None
    assert band.cheap_max < band.typical < band.expensive_min
    assert band.classify(band.cheap_max) == PriceLevel.CHEAP
    assert band.classify(band.typical) == PriceLevel.NORMAL
    assert band.classify(band.expensive_min) == PriceLevel.EXPENSIVE


@pytest.mark.asyncio
async def test_demo_price_band() -> None:
    provider = DemoPriceProvider()
    band = await provider.get_price_band("MOW", "AYT")
    assert band is not None
    assert band.sample_size >= 3
    assert "дёшево" in format_band_block(band)


def test_money_and_card_format() -> None:
    assert money(12345, "RUB") == "12 345 ₽"
    from flypingavia.services.prices import PriceBand, PriceQuote

    band = PriceBand(7000, 10000, 15000, sample_size=10)
    quote = PriceQuote(7200, "RUB", transfers=0, airline="S7", origin_code="OVB", destination_code="SGC")
    text = format_price_card(
        origin="OVB",
        destination="SGC",
        depart_date=date(2026, 7, 30),
        quote=quote,
        band=band,
        threshold=50000,
        watch_id=3,
        origin_name="Новосибирск",
        destination_name="Сургут",
        title="🔔 Цена ниже порога",
    )
    assert "Новосибирск" in text
    assert "Рынок по маршруту" in text
    assert "дёшево" in text
    assert "Ваш порог" in text
    assert "ниже порога" in text
    assert "Относительно рынка" in text
    assert "Пассажиры" not in text
    assert "Итого:" not in text


@pytest.mark.asyncio
async def test_resolve_moscow_city() -> None:
    place, cands = await resolve_place("Москва")
    assert place is not None
    assert place.code == "MOW"
    assert place.kind == "city"
    assert "SVO" in place.airport_codes
    assert "DME" in place.airport_codes
    assert "VKO" in place.airport_codes
    assert "ZIA" in place.airport_codes
    assert "XRK" not in place.airport_codes  # вокзал
    assert len(place.airport_codes) == 4
    assert len(place.search_codes) == 5  # MOW + 4 а/п


@pytest.mark.asyncio
async def test_resolve_alias_spb() -> None:
    place, _ = await resolve_place("Питер")
    assert place is not None
    assert place.code == "LED"


@pytest.mark.asyncio
async def test_cheapest_across_demo() -> None:
    provider = DemoPriceProvider()
    quote = await provider.get_cheapest_across(["MOW", "SVO", "DME"], ["AYT"])
    assert quote is not None
    assert quote.origin_code in {"MOW", "SVO", "DME"}
    assert len(quote.searched_origins) == 3


def test_flight_search_signature() -> None:
    from flypingavia.services.flight_search import make_signature

    # Пример из документации Travelpayouts (упрощённый)
    params = {
        "currency_code": "USD",
        "locale": "US",
        "marker": "YourMarker",
        "market_code": "US",
        "search_params": {
            "directions": [
                {"date": "2026-09-09", "destination": "NYC", "origin": "LAX"},
                {"date": "2026-09-25", "destination": "LAX", "origin": "NYC"},
            ],
            "passengers": {"adults": 1, "children": 0, "infants": 0},
            "trip_class": "Y",
        },
    }
    sig = make_signature("YourToken", params)
    assert len(sig) == 32
    assert sig == make_signature("YourToken", params)


@pytest.mark.asyncio
async def test_live_quote_preferred_when_client_returns(monkeypatch) -> None:
    from flypingavia.services.flight_search import LiveTicketQuote
    from flypingavia.services.prices import TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            return LiveTicketQuote(
                price=32155,
                currency="RUB",
                airline="S7",
                transfers=0,
                price_per_person=10718,
            )

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def boom(*args, **kwargs):
        raise AssertionError("Data API should not be used when live works")

    monkeypatch.setattr(provider, "get_cheapest_across", boom)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["SGC"],
        depart_date=date(2026, 7, 30),
        adults=2,
        children=1,
    )
    assert quote is not None
    assert quote.source == "live_search"
    assert quote.price == 32155
    assert quote.is_total_for_passengers is True


@pytest.mark.asyncio
async def test_live_quote_used_for_single_adult_when_preferred(monkeypatch) -> None:
    from flypingavia.services.flight_search import LiveTicketQuote
    from flypingavia.services.prices import TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            return LiveTicketQuote(price=27990, currency="RUB", transfers=1, price_per_person=27990)

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def boom(*args, **kwargs):
        raise AssertionError("Data API should not be used when prefer_live_for_quote is enabled")

    monkeypatch.setattr(provider, "get_cheapest_across", boom)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["IST"],
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        adults=1,
        prefer_live_for_quote=True,
    )
    assert quote is not None
    assert quote.source == "live_search"
    assert quote.fallback_reason is None
    assert quote.price == 27990


@pytest.mark.asyncio
async def test_live_timeout_falls_back_to_estimate(monkeypatch) -> None:
    from flypingavia.services.flight_search import FlightSearchTimeout
    from flypingavia.services.prices import PriceQuote, TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            raise FlightSearchTimeout("timeout")

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def fake_data(*args, **kwargs):
        return PriceQuote(price=37377, currency="RUB", source="travelpayouts")

    monkeypatch.setattr(provider, "get_cheapest_across", fake_data)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["IST"],
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        prefer_live_for_quote=True,
    )
    assert quote is not None
    assert quote.source == "travelpayouts"
    assert quote.fallback_reason == "live_timeout"


@pytest.mark.asyncio
async def test_live_no_results_falls_back_to_estimate(monkeypatch) -> None:
    from flypingavia.services.prices import PriceQuote, TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            return None

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def fake_data(*args, **kwargs):
        return PriceQuote(price=37377, currency="RUB", source="travelpayouts")

    monkeypatch.setattr(provider, "get_cheapest_across", fake_data)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["IST"],
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        prefer_live_for_quote=True,
    )
    assert quote is not None
    assert quote.source == "travelpayouts"
    assert quote.fallback_reason == "live_no_results"


@pytest.mark.asyncio
async def test_live_provider_error_falls_back_to_estimate(monkeypatch) -> None:
    from flypingavia.services.flight_search import FlightSearchError
    from flypingavia.services.prices import PriceQuote, TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            raise FlightSearchError("provider down")

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def fake_data(*args, **kwargs):
        return PriceQuote(price=37377, currency="RUB", source="travelpayouts")

    monkeypatch.setattr(provider, "get_cheapest_across", fake_data)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["IST"],
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        prefer_live_for_quote=True,
    )
    assert quote is not None
    assert quote.fallback_reason == "live_provider_error"


@pytest.mark.asyncio
async def test_live_access_denied_falls_back_to_estimate(monkeypatch) -> None:
    from flypingavia.services.flight_search import FlightSearchAccessDenied
    from flypingavia.services.prices import PriceQuote, TravelpayoutsPriceProvider

    class FakeLive:
        enabled = True
        access_denied = False

        async def search(self, **kwargs):
            raise FlightSearchAccessDenied("denied")

    provider = TravelpayoutsPriceProvider("tok", live_client=FakeLive(), live_mode="multi")

    async def fake_data(*args, **kwargs):
        return PriceQuote(price=37377, currency="RUB", source="travelpayouts")

    monkeypatch.setattr(provider, "get_cheapest_across", fake_data)
    quote = await provider.get_trip_quote(
        ["OVB"],
        ["IST"],
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        prefer_live_for_quote=True,
    )
    assert quote is not None
    assert quote.fallback_reason == "live_access_denied"