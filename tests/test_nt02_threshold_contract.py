"""NT-02: явный контракт порога X ≤ Y в тексте алерта."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from flypingavia.bot.formatters import format_price_card, format_threshold_contract, money
from flypingavia.db import repository as repo
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import PriceBand, PriceQuote
from tests.test_nt04_antispam import FixedPriceProvider


def _quote(price: float, currency: str = "RUB") -> PriceQuote:
    return PriceQuote(
        price=price,
        currency=currency,
        airline="SU",
        transfers=0,
        source="test",
        origin_code="MOW",
        destination_code="LED",
    )


def test_threshold_contract_price_below() -> None:
    block = format_threshold_contract(15_000, 20_000, "RUB")
    assert "Текущая цена: 15 000 ₽" in block
    assert "Ваш порог: 20 000 ₽" in block
    assert "15 000 ₽ ≤ 20 000 ₽" in block
    assert "Выгода к порогу: 5 000 ₽" in block
    assert "экономи" not in block.lower()


def test_threshold_contract_price_equal() -> None:
    block = format_threshold_contract(20_000, 20_000, "RUB")
    assert "Текущая цена: 20 000 ₽" in block
    assert "Ваш порог: 20 000 ₽" in block
    assert "20 000 ₽ ≤ 20 000 ₽" in block
    assert "Выгода к порогу: 0 ₽" in block
    assert "ниже порога на" not in block


def test_card_above_threshold_no_false_contract() -> None:
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(25_000),
        band=None,
        threshold=20_000,
        title="📊 Проверка",
    )
    assert "≤" not in text or "25 000 ₽ ≤" not in text
    assert "25 000 ₽ ≤ 20 000 ₽" not in text
    assert "до порога ещё 5 000 ₽" in text
    assert "Выгода к порогу" not in text


def test_card_without_threshold_no_contract() -> None:
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(15_000),
        band=PriceBand(10_000, 15_000, 20_000, sample_size=5),
        threshold=None,
    )
    assert "Ваш порог" not in text
    assert "Выгода к порогу" not in text
    assert "15 000 ₽ ≤ 20 000 ₽" not in text
    assert "Текущая цена:" not in text


def test_card_without_quote_with_threshold_ok() -> None:
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=None,
        quote=None,
        band=None,
        threshold=20_000,
        threshold_contract=True,
    )
    assert "Цена не найдена" in text
    assert "Ваш порог" in text
    assert "Выгода к порогу" not in text
    assert "20 000 ₽ ≤" not in text


def test_alert_card_includes_full_contract() -> None:
    text = format_price_card(
        origin="MOW",
        destination="LED",
        depart_date=date(2026, 8, 1),
        quote=_quote(15_000),
        band=None,
        threshold=20_000,
        title="🔔 Цена ≤ порога",
        watch_id=7,
        threshold_contract=True,
    )
    assert money(15_000) in text
    assert money(20_000) in text
    assert "15 000 ₽ ≤ 20 000 ₽" in text
    assert "Выгода к порогу: 5 000 ₽" in text
    assert text.count("<b>") == text.count("</b>")
    assert text.count("<code>") == text.count("</code>")


@pytest_asyncio.fixture
async def isolated_checker_env(tmp_path, monkeypatch):
    db_path = tmp_path / "nt02.db"
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
async def test_price_checker_alert_contains_threshold_contract(
    isolated_checker_env,
) -> None:
    settings = isolated_checker_env
    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=9202)
        await repo.add_watch(
            session,
            user=user,
            origin="MOW",
            destination="LED",
            max_price=20_000,
            depart_date=date.today() + timedelta(days=25),
        )

    bot = AsyncMock()
    bot.send_message = AsyncMock(return_value=MagicMock())
    provider = FixedPriceProvider(15_000)

    sent = await PriceChecker(bot=bot, settings=settings, provider=provider).run_once()
    assert sent == 1

    text = bot.send_message.await_args.kwargs["text"]
    assert "Текущая цена: 15 000 ₽" in text
    assert "Ваш порог: 20 000 ₽" in text
    assert "15 000 ₽ ≤ 20 000 ₽" in text
    assert "Выгода к порогу: 5 000 ₽" in text
