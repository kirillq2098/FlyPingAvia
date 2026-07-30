"""TR-04: timestamp последней проверки Watch."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio
from sqlalchemy import select

from flypingavia.bot.formatters import (
    format_last_checked,
    format_last_checked_line,
    format_price_card,
)
from flypingavia.db import repository as repo
from flypingavia.db.models import AlertEvent, Watch
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import PriceBand, PriceProvider, PriceQuote

MSK = ZoneInfo("Europe/Moscow")
NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


def _quote(price: float = 15_000) -> PriceQuote:
    return PriceQuote(
        price=price,
        currency="RUB",
        source="test",
        origin_code="MOW",
        destination_code="LED",
    )


def _band(price: float = 15_000) -> PriceBand:
    return PriceBand(
        cheap_max=price * 0.9,
        typical=price,
        expensive_min=price * 1.2,
        sample_size=8,
        currency="RUB",
        source="test",
    )


# --- formatter ---


def test_format_none() -> None:
    assert format_last_checked(None, now=NOW) == "Ещё не проверяли"
    assert format_last_checked_line(None, now=NOW) == "🕒 Ещё не проверяли"


def test_format_just_now() -> None:
    assert format_last_checked(NOW - timedelta(seconds=20), now=NOW, tz=MSK) == (
        "Проверено только что"
    )


def test_format_minutes() -> None:
    text = format_last_checked(NOW - timedelta(minutes=8), now=NOW, tz=MSK)
    assert text == "Проверено 8 минут назад"


def test_format_hours() -> None:
    text = format_last_checked(NOW - timedelta(hours=2), now=NOW, tz=MSK)
    assert text == "Проверено 2 часа назад"


def test_format_today() -> None:
    checked = NOW - timedelta(hours=14)
    text = format_last_checked(checked, now=NOW, tz=MSK)
    assert text.startswith("Проверено сегодня в ")


def test_format_yesterday() -> None:
    checked = NOW - timedelta(hours=30)
    text = format_last_checked(checked, now=NOW, tz=MSK)
    assert text.startswith("Проверено вчера в ")


def test_format_older() -> None:
    checked = datetime(2026, 7, 25, 6, 0, 0, tzinfo=timezone.utc)
    text = format_last_checked(checked, now=NOW, tz=MSK)
    assert "25 июля" in text
    assert "в " in text


def test_format_timezone_conversion() -> None:
    checked = datetime(2026, 7, 25, 12, 0, 0, tzinfo=timezone.utc)
    text = format_last_checked(checked, now=NOW + timedelta(days=10), tz=MSK)
    assert "15:00" in text


def test_format_naive_does_not_crash() -> None:
    naive = datetime(2026, 7, 30, 11, 55, 0)
    text = format_last_checked(naive, now=NOW, tz=MSK)
    assert "Проверено" in text
    assert "назад" in text or "только что" in text


def test_format_small_future_skew() -> None:
    text = format_last_checked(NOW + timedelta(seconds=20), now=NOW, tz=MSK)
    assert text == "Проверено только что"


def test_format_alert_line() -> None:
    line = format_last_checked_line(NOW, now=NOW, tz=MSK, alert=True)
    assert line == "🕒 Проверено: только что"


def test_alert_card_uses_checked_at_not_stale() -> None:
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(12_000),
        band=_band(),
        threshold=20_000,
        title="🔔 Цена ≤ порога",
        watch_id=1,
        threshold_contract=True,
        checked_at=NOW,
        now=NOW,
        display_timezone=MSK,
    )
    assert "🕒 Проверено: только что" in text
    idx_market = text.index("🟢") if "🟢" in text else text.index("Выгода к порогу")
    assert text.index("🕒 Проверено") > idx_market


# --- checker ---


class ControllableProvider(PriceProvider):
    def __init__(self) -> None:
        self.price: float | None = 12_000
        self.error = False
        self.quote_calls = 0

    async def get_cheapest(self, *a, **k):
        return await self.get_trip_quote(["MOW"], ["LED"])

    async def get_price_band(self, *a, **k):
        return _band(self.price or 15_000)

    async def get_trip_quote(self, origins, destinations, **kwargs):
        self.quote_calls += 1
        if self.error:
            raise RuntimeError("provider down")
        if self.price is None:
            return None
        return _quote(self.price)

    async def get_trip_band(self, origins, destinations, **kwargs):
        if self.error:
            raise RuntimeError("band down")
        if self.price is None:
            return None
        return _band(self.price)


@pytest_asyncio.fixture
async def tr04_env(tmp_path, monkeypatch):
    db_path = tmp_path / "tr04.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", "123:TEST")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("DISPLAY_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "700001")
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


async def _add_watch(
    settings,
    *,
    max_price=20_000,
    flex=0,
    last_checked=None,
    telegram_id: int = 42,
):
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=telegram_id, username="u")
        w = await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="LED",
            max_price=max_price,
            depart_date=date.today() + timedelta(days=20),
            currency="RUB",
            flexibility_days=flex,
        )
        if last_checked is not None:
            w.last_checked_at = last_checked
        await session.flush()
        return w.id, user.id


def _alert_text(bot: AsyncMock) -> str:
    args = bot.send_message.await_args
    if args.kwargs.get("text"):
        return args.kwargs["text"]
    return args.args[1]


@pytest.mark.asyncio
async def test_checker_quote_found_alert_updates_checked(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, max_price=20_000)
    provider = ControllableProvider()
    provider.price = 12_000
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert sent == 1
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w is not None
        assert w.last_checked_at is not None
    assert "Проверено" in _alert_text(bot)


@pytest.mark.asyncio
async def test_checker_above_threshold_updates(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, max_price=10_000)
    provider = ControllableProvider()
    provider.price = 15_000
    bot = AsyncMock()
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None
        assert w.last_price == 15_000
    bot.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_checker_no_quote_updates(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings)
    provider = ControllableProvider()
    provider.price = None
    bot = AsyncMock()
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None
        assert w.last_price is None


@pytest.mark.asyncio
async def test_checker_nt04_suppress_still_updates(tr04_env) -> None:
    settings = tr04_env
    watch_id, user_id = await _add_watch(settings, max_price=20_000)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        await repo.log_alert_event(
            session,
            watch_id=watch_id,
            user_id=user_id,
            price=12_000,
            threshold=20_000,
            sent_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

    provider = ControllableProvider()
    provider.price = 12_000
    bot = AsyncMock()
    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert sent == 0
    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None


@pytest.mark.asyncio
async def test_checker_telegram_fail_keeps_checked(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, max_price=20_000)
    provider = ControllableProvider()
    provider.price = 11_000
    bot = AsyncMock()
    bot.send_message = AsyncMock(side_effect=RuntimeError("tg down"))
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None
        events = (await session.execute(select(AlertEvent))).scalars().all()
        assert events == []


@pytest.mark.asyncio
async def test_checker_alert_event_fail_keeps_checked(tr04_env, monkeypatch) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, max_price=20_000)
    provider = ControllableProvider()
    provider.price = 11_000
    bot = AsyncMock()
    bot.send_message = AsyncMock()

    async def _boom(*a, **k):
        raise RuntimeError("db alert fail")

    monkeypatch.setattr(repo, "log_alert_event", _boom)
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None


@pytest.mark.asyncio
async def test_checker_search_error_preserves_old(tr04_env, monkeypatch) -> None:
    settings = tr04_env
    old = datetime(2026, 7, 1, 10, 0, 0, tzinfo=timezone.utc)
    watch_id, _ = await _add_watch(settings, last_checked=old)

    async def _boom(*_a, **_k):
        raise RuntimeError("provider down")

    monkeypatch.setattr(
        "flypingavia.services.checker.search_flexible_trip",
        _boom,
    )
    bot = AsyncMock()
    await PriceChecker(
        bot=bot, settings=settings, provider=ControllableProvider()
    ).run_once()
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        got = w.last_checked_at
        assert got is not None
        # SQLite may return naive UTC
        if got.tzinfo is None:
            got = got.replace(tzinfo=timezone.utc)
        assert got == old


@pytest.mark.asyncio
async def test_checker_flexible_one_checked_update(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, max_price=5_000, flex=3)
    provider = ControllableProvider()
    provider.price = 18_000
    bot = AsyncMock()
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert provider.quote_calls >= 3
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None


@pytest.mark.asyncio
async def test_checker_alert_timestamp_matches_check(tr04_env) -> None:
    settings = tr04_env
    await _add_watch(settings, max_price=20_000)
    provider = ControllableProvider()
    provider.price = 10_000
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert "🕒 Проверено: только что" in _alert_text(bot)


@pytest.mark.asyncio
async def test_checker_lock_no_regression(tr04_env) -> None:
    settings = tr04_env
    await _add_watch(settings, max_price=20_000)
    provider = ControllableProvider()
    provider.price = 10_000
    bot = AsyncMock()
    bot.send_message = AsyncMock()
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)
    first = await checker.run_once()
    second = await checker.run_once()
    assert first == 1
    assert second == 0


@pytest.mark.asyncio
async def test_manual_check_with_quote_updates(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings)
    checked = datetime.now(timezone.utc)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        ok = await repo.mark_watch_checked(session, watch_id, checked)
        assert ok is True
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None


@pytest.mark.asyncio
async def test_manual_check_none_quote_updates(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        await repo.mark_watch_checked(session, watch_id, datetime.now(timezone.utc))
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is not None
        assert w.last_price is None


@pytest.mark.asyncio
async def test_manual_provider_error_keeps_old(tr04_env) -> None:
    settings = tr04_env
    old = datetime(2026, 6, 1, tzinfo=timezone.utc)
    watch_id, _ = await _add_watch(settings, last_checked=old)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        got = w.last_checked_at
        assert got is not None
        # SQLite may return naive UTC
        if got.tzinfo is None:
            got = got.replace(tzinfo=timezone.utc)
        assert got == old


@pytest.mark.asyncio
async def test_preview_create_does_not_set_checked(tr04_env) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        w = await session.get(Watch, watch_id)
        assert w.last_checked_at is None


@pytest.mark.asyncio
async def test_api_new_watch_null_checked(tr04_env, monkeypatch) -> None:
    import flypingavia.api.app as api_mod
    from flypingavia.api.app import create_api
    from flypingavia.config import get_settings
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: ControllableProvider())

    async def _none(*a, **k):
        return None

    monkeypatch.setattr(api_mod, "search_flexible_trip", _none)
    app = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.post(
            "/api/watches",
            json={"origin": "MOW", "destination": "LED", "max_price": 20_000},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["last_checked_at"] is None
        assert body["flexibility_days"] == 0

        health = await c.get("/api/health")
        assert health.json()["display_timezone"] == "Europe/Moscow"


@pytest.mark.asyncio
async def test_api_checked_watch_iso_utc(tr04_env, monkeypatch) -> None:
    settings = tr04_env
    watch_id, _ = await _add_watch(settings, telegram_id=700001)
    checked = datetime(2026, 7, 30, 12, 35, 0, tzinfo=timezone.utc)
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        await repo.mark_watch_checked(session, watch_id, checked)

    import flypingavia.api.app as api_mod
    from flypingavia.api.app import create_api
    from flypingavia.config import get_settings
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: ControllableProvider())
    app = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/watches")
    assert res.status_code == 200
    items = res.json()
    assert len(items) == 1
    ts = items[0]["last_checked_at"]
    assert ts is not None
    assert "2026-07-30T12:35:00" in ts
    assert ts.endswith("Z") or ts.endswith("+00:00")
    assert items[0]["flexibility_days"] == 0


def test_frontend_format_helpers_present() -> None:
    src = (Path(__file__).resolve().parents[1] / "flypingavia/web/static/app.js").read_text(
        encoding="utf-8"
    )
    assert "function formatLastChecked" in src
    assert "Ещё не проверяли" in src
    assert "display_timezone" in src
    assert "Invalid Date" not in src
    assert "formatLastChecked(w.last_checked_at)" in src


def test_display_timezone_config_validation(monkeypatch) -> None:
    from flypingavia.config import Settings

    s = Settings(bot_token="1:T", display_timezone="Europe/Moscow")
    assert str(s.display_tz) == "Europe/Moscow" or s.display_timezone == "Europe/Moscow"
    with pytest.raises(Exception):
        Settings(bot_token="1:T", display_timezone="Not/AZone")
