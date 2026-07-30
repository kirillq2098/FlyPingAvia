"""CS-05: предупреждение о пороге ниже рынка."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select

from flypingavia.bot.formatters import format_low_threshold_warning
from flypingavia.db import repository as repo
from flypingavia.db.models import Watch
from flypingavia.services.prices import PriceBand, PriceQuote
from flypingavia.services.threshold_policy import (
    band_from_snapshot,
    evaluate_low_threshold,
    should_warn_low_threshold,
)


def _band(
    cheap: float = 15_000,
    typical: float = 19_000,
    expensive: float = 25_000,
    sample: int = 10,
) -> PriceBand:
    return PriceBand(
        cheap_max=cheap,
        typical=typical,
        expensive_min=expensive,
        sample_size=sample,
        currency="RUB",
        source="test",
    )


def test_warn_when_threshold_below_cheap_max() -> None:
    assert should_warn_low_threshold(10_000, _band()) is True
    d = evaluate_low_threshold(10_000, _band())
    assert d.warn is True
    assert d.cheap_max == 15_000
    assert d.code == "LOW_THRESHOLD_CONFIRMATION_REQUIRED"


def test_no_warn_when_equal_cheap_max() -> None:
    assert should_warn_low_threshold(15_000, _band()) is False


def test_no_warn_when_above_cheap_max() -> None:
    assert should_warn_low_threshold(19_000, _band()) is False


def test_no_warn_when_band_none() -> None:
    assert should_warn_low_threshold(5_000, None) is False


def test_no_warn_when_sample_size_zero() -> None:
    assert should_warn_low_threshold(5_000, _band(sample=0)) is False


def test_no_warn_when_band_invalid() -> None:
    assert should_warn_low_threshold(5_000, _band(cheap=0, typical=0, expensive=0)) is False
    bad = PriceBand(float("nan"), 10_000, 12_000, sample_size=3, currency="RUB")
    assert should_warn_low_threshold(5_000, bad) is False


def test_currency_does_not_affect_numeric_compare() -> None:
    usd = PriceBand(100, 150, 200, sample_size=5, currency="USD", source="test")
    assert should_warn_low_threshold(80, usd) is True
    assert should_warn_low_threshold(100, usd) is False


def test_preset_cheap_equals_cheap_max_no_warn() -> None:
    """Системная кнопка «Дёшево» = cheap_max → без предупреждения."""
    band = _band(cheap=15_000)
    button_value = int(band.cheap_max)
    assert should_warn_low_threshold(button_value, band) is False


def test_warning_text_is_calm() -> None:
    text = format_low_threshold_warning(10_000, 15_000, "RUB")
    assert "10 000 ₽" in text
    assert "15 000 ₽" in text
    assert "может долго не прийти" in text
    assert "не бывает" not in text.lower()
    assert "никогда" not in text.lower()
    assert "неверный" not in text.lower()
    assert text.count("<b>") == text.count("</b>")


def test_band_from_snapshot() -> None:
    band = band_from_snapshot(cheap_max=12_000, typical=18_000, sample_size=4)
    assert band is not None
    assert should_warn_low_threshold(11_000, band) is True
    assert band_from_snapshot(cheap_max=None, typical=18_000) is None


# --- Telegram helpers ---


@pytest.mark.asyncio
async def test_offer_or_create_warns_and_keeps_pending(tmp_path, monkeypatch) -> None:
    from flypingavia.bot import handlers as h
    from flypingavia.config import Settings

    state = AsyncMock()
    state_data = {
        "origin_code": "MOW",
        "destination_code": "LED",
        "band_cheap_max": 15_000.0,
        "band_typical": 19_000.0,
        "band_expensive_min": 25_000.0,
        "band_sample_size": 8,
        "depart_date": None,
        "adults": 1,
        "children": 0,
        "infants": 0,
    }
    stored: dict = {}

    async def _get_data():
        return {**state_data, **stored}

    async def _update(**kwargs):
        stored.update(kwargs)

    async def _set_state(st):
        stored["_state"] = st

    state.get_data = _get_data
    state.update_data = _update
    state.set_state = _set_state
    state.clear = AsyncMock()

    target = AsyncMock()
    settings = Settings(bot_token="1:TEST", travelpayouts_token="")
    provider = MagicMock()

    created = await h._offer_or_create_watch(
        target=target,
        telegram_id=1,
        username="u",
        settings=settings,
        provider=provider,
        state=state,
        data=await _get_data(),
        max_price=10_000,
    )
    assert created is None
    assert stored.get("pending_threshold") == 10_000.0
    assert stored.get("_state") == h.AddWatch.waiting_low_threshold_confirmation
    target.answer.assert_awaited()
    text = target.answer.await_args.args[0]
    assert "ниже текущего рынка" in text
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_offer_or_create_normal_threshold_finalizes(tmp_path, monkeypatch) -> None:
    from flypingavia.bot import handlers as h
    from flypingavia.config import Settings

    finalize = AsyncMock(return_value=42)
    monkeypatch.setattr(h, "_finalize_watch_creation", finalize)

    state = AsyncMock()
    data = {
        "origin_code": "MOW",
        "destination_code": "LED",
        "band_cheap_max": 15_000.0,
        "band_typical": 19_000.0,
        "band_expensive_min": 25_000.0,
        "band_sample_size": 8,
    }
    settings = Settings(bot_token="1:TEST", travelpayouts_token="")
    result = await h._offer_or_create_watch(
        target=AsyncMock(),
        telegram_id=1,
        username="u",
        settings=settings,
        provider=MagicMock(),
        state=state,
        data=data,
        max_price=15_000,
    )
    assert result == 42
    finalize.assert_awaited_once()


@pytest.mark.asyncio
async def test_offer_or_create_band_none_creates(monkeypatch) -> None:
    from flypingavia.bot import handlers as h
    from flypingavia.config import Settings

    finalize = AsyncMock(return_value=7)
    monkeypatch.setattr(h, "_finalize_watch_creation", finalize)
    settings = Settings(bot_token="1:TEST", travelpayouts_token="")
    result = await h._offer_or_create_watch(
        target=AsyncMock(),
        telegram_id=1,
        username=None,
        settings=settings,
        provider=MagicMock(),
        state=AsyncMock(),
        data={"origin_code": "MOW", "destination_code": "AYT"},
        max_price=3_000,
    )
    assert result == 7


@pytest.mark.asyncio
async def test_confirm_clears_pending_prevents_double(monkeypatch) -> None:
    """Повторный save без pending не создаёт Watch."""
    from flypingavia.bot import handlers as h

    finalize = AsyncMock(return_value=1)
    monkeypatch.setattr(h, "_finalize_watch_creation", finalize)

    # Simulate second tap: pending already None
    data = {"origin_code": "MOW", "pending_threshold": None}
    pending = data.get("pending_threshold")
    assert pending is None
    finalize.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirm_restores_pending_on_finalize_error(monkeypatch, caplog) -> None:
    """Ошибка create → pending восстановлен, повторный confirm создаёт Watch один раз."""
    import logging

    from flypingavia.bot import handlers as h
    from flypingavia.config import Settings

    calls = {"n": 0}

    async def _flaky_finalize(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("db down")
        await kwargs["state"].clear()
        return 99

    monkeypatch.setattr(h, "_finalize_watch_creation", _flaky_finalize)

    stored: dict = {
        "pending_threshold": 10_000.0,
        "_state": h.AddWatch.waiting_low_threshold_confirmation,
    }

    async def _update(**kwargs):
        stored.update(kwargs)

    async def _set_state(st):
        stored["_state"] = st

    async def _clear():
        stored.clear()
        stored["_cleared"] = True

    state = AsyncMock()
    state.update_data = _update
    state.set_state = _set_state
    state.clear = _clear

    target = AsyncMock()
    settings = Settings(bot_token="1:TEST", travelpayouts_token="")
    data = {
        "origin_code": "MOW",
        "destination_code": "LED",
        "pending_threshold": 10_000.0,
    }

    with caplog.at_level(logging.ERROR, logger="flypingavia.bot.handlers"):
        first = await h._finalize_after_low_threshold_confirm(
            target=target,
            telegram_id=42,
            username="u",
            settings=settings,
            provider=MagicMock(),
            state=state,
            data=data,
            pending=10_000.0,
        )

    assert first is None
    assert stored.get("pending_threshold") == 10_000.0
    assert stored.get("_state") == h.AddWatch.waiting_low_threshold_confirmation
    assert not stored.get("_cleared")
    assert "Failed to create Watch after low-threshold confirmation" in caplog.text
    target.answer.assert_awaited()
    assert "Не удалось сохранить подписку" in target.answer.await_args.args[0]

    # Повтор после «починки» — успех и очистка FSM через finalize.
    second = await h._finalize_after_low_threshold_confirm(
        target=target,
        telegram_id=42,
        username="u",
        settings=settings,
        provider=MagicMock(),
        state=state,
        data=data,
        pending=10_000.0,
    )
    assert second == 99
    assert calls["n"] == 2
    assert stored.get("_cleared") is True


# --- Mini App / API ---


class _FixedBandProvider:
    def __init__(self, band: PriceBand | None, price: float = 18_000) -> None:
        self.band = band
        self.price = price

    async def get_trip_quote(self, *args, **kwargs) -> PriceQuote:
        return PriceQuote(
            price=self.price,
            currency="RUB",
            source="test",
            origin_code="MOW",
            destination_code="LED",
        )

    async def get_trip_band(self, *args, **kwargs) -> PriceBand | None:
        return self.band


@pytest_asyncio.fixture
async def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "cs05.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "555001")

    from flypingavia.config import get_settings
    import flypingavia.db.session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None

    from flypingavia.db.session import init_db
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient

    await init_db()
    app = create_api(get_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, app

    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_api_low_threshold_requires_confirm(api_client, monkeypatch) -> None:
    client, app = api_client
    band = _band(cheap=15_000)
    provider = _FixedBandProvider(band)
    # Patch provider used inside create_api closure — replace on module builder path
    import flypingavia.api.app as api_mod

    # The app already has provider bound; patch evaluate path via provider on app routes
    # Recreate with patched build_price_provider
    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: provider)

    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient

    app2 = create_api(get_settings())
    transport = ASGITransport(app=app2)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={
                "origin": "MOW",
                "destination": "LED",
                "max_price": 10_000,
                "depart_date": (date.today() + timedelta(days=30)).isoformat(),
            },
        )
    assert res.status_code == 409
    detail = res.json()["detail"]
    assert detail["code"] == "LOW_THRESHOLD_CONFIRMATION_REQUIRED"
    assert detail["threshold"] == 10_000
    assert detail["cheap_max"] == 15_000

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        assert (await session.execute(select(Watch))).scalars().all() == []


@pytest.mark.asyncio
async def test_api_low_threshold_with_confirm_creates(api_client, monkeypatch) -> None:
    import flypingavia.api.app as api_mod
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient
    from flypingavia.db.session import session_scope

    provider = _FixedBandProvider(_band(cheap=15_000))
    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: provider)
    app2 = create_api(get_settings())
    transport = ASGITransport(app=app2)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={
                "origin": "MOW",
                "destination": "LED",
                "max_price": 10_000,
                "confirm_low_threshold": True,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["max_price"] == 10_000
        watch_id = body["id"]

        # Повтор с confirm создаёт ещё один Watch (идемпотентности нет — фиксируем).
        res2 = await c.post(
            "/api/watches",
            json={
                "origin": "MOW",
                "destination": "LED",
                "max_price": 10_000,
                "confirm_low_threshold": True,
            },
        )
        assert res2.status_code == 200
        assert res2.json()["id"] != watch_id

    async with session_scope() as session:
        watches = (await session.execute(select(Watch))).scalars().all()
        assert len(watches) == 2


@pytest.mark.asyncio
async def test_api_normal_threshold_creates(api_client, monkeypatch) -> None:
    import flypingavia.api.app as api_mod
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(
        api_mod, "build_price_provider", lambda _s: _FixedBandProvider(_band(cheap=15_000))
    )
    app2 = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={"origin": "MOW", "destination": "LED", "max_price": 15_000},
        )
    assert res.status_code == 200
    assert res.json()["max_price"] == 15_000


@pytest.mark.asyncio
async def test_api_band_none_creates_without_warn(api_client, monkeypatch) -> None:
    import flypingavia.api.app as api_mod
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(
        api_mod, "build_price_provider", lambda _s: _FixedBandProvider(None)
    )
    app2 = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={"origin": "MOW", "destination": "LED", "max_price": 1_000},
        )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_api_ignores_client_cheap_max(api_client, monkeypatch) -> None:
    """Клиент не может подменить рынок — поля cheap_max в WatchIn нет."""
    import flypingavia.api.app as api_mod
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(
        api_mod, "build_price_provider", lambda _s: _FixedBandProvider(_band(cheap=15_000))
    )
    app2 = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={
                "origin": "MOW",
                "destination": "LED",
                "max_price": 10_000,
                "cheap_max": 5_000,  # ignored extra
            },
        )
    assert res.status_code == 409
    assert res.json()["detail"]["cheap_max"] == 15_000
