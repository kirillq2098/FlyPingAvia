"""NT-03: рыночная оценка 🟢/🟡/🔴 в алерте PriceChecker."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy import select

from flypingavia.bot.formatters import format_market_assessment, format_price_card, money
from flypingavia.db import repository as repo
from flypingavia.db.models import AlertEvent
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import PriceBand, PriceProvider, PriceQuote, align_band_to_quote


def _quote(price: float, *, return_date: date | None = None) -> PriceQuote:
    return PriceQuote(
        price=price,
        currency="RUB",
        airline="SU",
        transfers=0,
        source="test",
        origin_code="MOW",
        destination_code="LED",
        return_date=return_date,
    )


def _band(*, cheap: float, typical: float, expensive: float, sample: int = 10) -> PriceBand:
    return PriceBand(
        cheap_max=cheap,
        typical=typical,
        expensive_min=expensive,
        sample_size=sample,
        currency="RUB",
        source="test",
    )


def _alert_card(price: float, threshold: float, band: PriceBand | None, **kwargs) -> str:
    return format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(price, return_date=kwargs.pop("return_date", None)),
        band=band,
        threshold=threshold,
        title="🔔 Цена ≤ порога",
        watch_id=1,
        threshold_contract=True,
        **kwargs,
    )


def test_market_assessment_cheap() -> None:
    band = _band(cheap=16_000, typical=19_000, expensive=25_000)
    block = format_market_assessment(14_000, band, "RUB")
    assert block is not None
    assert "🟢" in block
    assert "дёшево" in block.lower()
    assert "около 19 000 ₽" in block
    assert "лучшая" not in block.lower()


def test_market_assessment_normal() -> None:
    band = _band(cheap=12_000, typical=19_000, expensive=25_000)
    block = format_market_assessment(19_000, band, "RUB")
    assert block is not None
    assert "🟡" in block
    assert "обычн" in block.lower()
    assert "около 19 000 ₽" in block
    assert "выгод" not in block.lower()  # нет рыночной «выгоды»


def test_market_assessment_expensive() -> None:
    band = _band(cheap=12_000, typical=19_000, expensive=22_000)
    block = format_market_assessment(24_000, band, "RUB")
    assert block is not None
    assert "🔴" in block
    assert "дороже" in block.lower()
    assert "около 19 000 ₽" in block
    assert "20 000" not in block  # порог не подставляется


def test_market_assessment_none_band() -> None:
    assert format_market_assessment(15_000, None, "RUB") is None


def test_market_assessment_incomplete_sample() -> None:
    band = _band(cheap=10_000, typical=15_000, expensive=20_000, sample=0)
    assert format_market_assessment(12_000, band, "RUB") is None


def test_market_assessment_invalid_typical() -> None:
    band = PriceBand(0, 0, 0, sample_size=5, currency="RUB", source="test")
    assert format_market_assessment(10_000, band, "RUB") is None


def test_alert_cheap_keeps_nt02_and_market() -> None:
    band = _band(cheap=16_000, typical=19_000, expensive=25_000)
    text = _alert_card(14_000, 30_000, band)
    assert "14 000 ₽ ≤ 30 000 ₽" in text
    assert "Выгода к порогу: 16 000 ₽" in text
    assert "🟢" in text
    assert "дёшево" in text.lower()
    assert "около 19 000 ₽" in text
    # порядок: контракт до рынка
    assert text.index("Выгода к порогу") < text.index("🟢")
    assert "Рынок по маршруту" not in text  # компактный блок, не таблица вилки


def test_alert_normal_zone() -> None:
    band = _band(cheap=12_000, typical=19_000, expensive=25_000)
    text = _alert_card(18_500, 40_000, band)
    assert "🟡" in text
    assert "Обычная цена" in text
    assert "18 500 ₽ ≤ 40 000 ₽" in text
    assert "выгодн" not in text.lower() or "Выгода к порогу" in text


def test_alert_expensive_vs_market_high_threshold() -> None:
    """Цена ≤ высокого порога, но 🔴 относительно рынка."""
    band = _band(cheap=12_000, typical=19_000, expensive=22_000)
    text = _alert_card(24_000, 50_000, band)
    assert "🔴" in text
    assert "Дороже обычного" in text
    assert "24 000 ₽ ≤ 50 000 ₽" in text
    assert "Выгода к порогу: 26 000 ₽" in text
    assert "Ваш порог: 50 000 ₽" in text
    # ориентир — typical, не порог
    assert "около 19 000 ₽" in text
    assert text.count("50 000 ₽") == 2  # порог в двух строках контракта, не в рынке


def test_alert_band_none_fallback() -> None:
    text = _alert_card(15_000, 20_000, None)
    assert "15 000 ₽ ≤ 20 000 ₽" in text
    assert "Выгода к порогу: 5 000 ₽" in text
    assert "🟢" not in text and "🟡" not in text and "🔴" not in text
    assert "Рынок по маршруту" not in text
    assert "None" not in text
    assert "\n\n\n" not in text


def test_alert_round_trip_neutral_orient() -> None:
    band = _band(cheap=20_000, typical=38_000, expensive=50_000)
    text = _alert_card(22_000, 45_000, band, return_date=date(2026, 8, 15))
    assert "Ориентир по текущим данным: около 38 000 ₽" in text
    assert "Туда+обратно ≈ сумма двух one-way" in text


def test_non_alert_card_keeps_full_band_block() -> None:
    band = _band(cheap=10_000, typical=15_000, expensive=20_000)
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(9_000),
        band=band,
        threshold=None,
    )
    assert "Рынок по маршруту" in text
    assert "Относительно рынка:" in text


class ControllableBandProvider(PriceProvider):
    """Фиксированная цена + управляемый band для интеграционных тестов NT-03."""

    def __init__(self, price: float, band: PriceBand | None) -> None:
        self.price = float(price)
        self.band = band
        self.trip_band_calls = 0

    async def get_cheapest(self, *args, **kwargs) -> Optional[PriceQuote]:
        return None

    async def get_price_band(self, *args, **kwargs) -> Optional[PriceBand]:
        return self.band

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
        o = origins[0].upper() if origins else "XXX"
        d = destinations[0].upper() if destinations else "YYY"
        return PriceQuote(
            price=self.price,
            currency=currency.upper(),
            airline="SU",
            transfers=0,
            source="test",
            origin_code=o,
            destination_code=d,
            adults=adults,
            children=children,
            infants=infants,
            return_date=return_date,
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
        _ = (origins, destinations, depart_date, return_date, adults, children, infants, currency)
        self.trip_band_calls += 1
        return self.band


@pytest_asyncio.fixture
async def isolated_checker_env(tmp_path, monkeypatch):
    db_path = tmp_path / "nt03.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")

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
async def test_price_checker_alert_includes_market_and_alert_event(
    isolated_checker_env,
    monkeypatch,
) -> None:
    settings = isolated_checker_env
    from flypingavia.db.session import session_scope
    import flypingavia.services.checker as checker_mod

    align_calls: list[tuple] = []
    real_align = align_band_to_quote

    def _tracking_align(band, quote):
        align_calls.append((band, quote))
        return real_align(band, quote)

    monkeypatch.setattr(checker_mod, "align_band_to_quote", _tracking_align)

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=9303)
        await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="LED",
            max_price=40_000,
            depart_date=date.today() + timedelta(days=20),
        )

    band = _band(cheap=16_000, typical=19_000, expensive=25_000)
    provider = ControllableBandProvider(14_000, band)
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert sent == 1
    assert provider.trip_band_calls >= 1
    assert len(align_calls) >= 1

    text = bot.send_message.await_args.kwargs["text"]
    assert "🟢" in text
    assert "дёшево" in text.lower()
    assert "около 19 000 ₽" in text
    assert "14 000 ₽ ≤ 40 000 ₽" in text

    async with session_scope() as session:
        events = (await session.execute(select(AlertEvent))).scalars().all()
        assert len(events) == 1
        assert events[0].price == 14_000


@pytest.mark.asyncio
async def test_price_checker_alert_without_band(isolated_checker_env) -> None:
    settings = isolated_checker_env
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=9304)
        await repo.add_watch(
            session,
            user=user,
            origin="SVO",
            destination="AER",
            max_price=30_000,
            depart_date=date.today() + timedelta(days=15),
        )

    provider = ControllableBandProvider(12_000, None)
    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert sent == 1
    text = bot.send_message.await_args.kwargs["text"]
    assert "12 000 ₽ ≤ 30 000 ₽" in text
    assert "🟢" not in text
    assert "None" not in text
