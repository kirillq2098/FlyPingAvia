"""CS-07 MVP: unit-тесты окна гибких дат."""

from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from flypingavia.services.flexible_dates import (
    ALLOWED_FLEXIBILITY_DAYS,
    DateCandidate,
    build_date_candidates,
    search_flexible_trip,
    validate_flexibility_days,
)
from flypingavia.services.prices import PriceQuote


def test_exact_one_candidate() -> None:
    dep = date(2026, 8, 15)
    cands = build_date_candidates(dep, None, 0, today=date(2026, 8, 1))
    assert len(cands) == 1
    assert cands[0] == DateCandidate(dep, None, 0)


@pytest.mark.parametrize(
    ("flex", "expected"),
    [(1, 3), (3, 7), (7, 15)],
)
def test_window_sizes(flex: int, expected: int) -> None:
    dep = date(2026, 8, 15)
    cands = build_date_candidates(dep, None, flex, today=date(2026, 8, 1))
    assert len(cands) == expected
    assert [c.offset_days for c in cands] == list(range(-flex, flex + 1))


def test_past_dates_filtered() -> None:
    today = date(2026, 8, 15)
    dep = date(2026, 8, 15)
    cands = build_date_candidates(dep, None, 3, today=today)
    assert all(c.depart_date >= today for c in cands)
    assert cands[0].offset_days == 0
    assert len(cands) == 4  # 0..+3


def test_round_trip_same_offset_preserves_duration() -> None:
    dep = date(2026, 8, 15)
    ret = date(2026, 8, 22)
    cands = build_date_candidates(dep, ret, 3, today=date(2026, 8, 1))
    assert len(cands) == 7
    for c in cands:
        assert c.return_date is not None
        assert (c.return_date - c.depart_date).days == 7
        assert c.depart_date == dep + timedelta(days=c.offset_days)
        assert c.return_date == ret + timedelta(days=c.offset_days)


def test_invalid_flexibility_rejected() -> None:
    for bad in (-1, 2, 100, 1.5, "3", True):
        with pytest.raises(ValueError):
            validate_flexibility_days(bad)  # type: ignore[arg-type]
    assert validate_flexibility_days(None) == 0
    assert ALLOWED_FLEXIBILITY_DAYS == frozenset({0, 1, 3, 7})


def test_leap_year_and_month_boundary() -> None:
    dep = date(2024, 2, 28)
    cands = build_date_candidates(dep, None, 1, today=date(2024, 2, 1))
    assert [c.depart_date for c in cands] == [
        date(2024, 2, 27),
        date(2024, 2, 28),
        date(2024, 2, 29),
    ]
    dep2 = date(2026, 8, 31)
    cands2 = build_date_candidates(dep2, None, 1, today=date(2026, 8, 1))
    assert cands2[-1].depart_date == date(2026, 9, 1)


@pytest.mark.asyncio
async def test_search_picks_min_price_and_found_dates() -> None:
    prices = {
        date(2026, 8, 14): 20_000,
        date(2026, 8, 15): 18_000,
        date(2026, 8, 16): 12_000,
    }

    class P:
        async def get_trip_quote(self, origins, destinations, **kwargs):
            d = kwargs.get("depart_date")
            if d not in prices:
                return None
            return PriceQuote(price=prices[d], currency="RUB", source="test", origin_code="MOW", destination_code="AER")

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["AER"],
        depart_date=date(2026, 8, 15),
        flexibility_days=1,
        today=date(2026, 8, 1),
    )
    assert result is not None
    assert result.quote.price == 12_000
    assert result.found_depart_date == date(2026, 8, 16)
    assert result.offset_days == 1
    assert result.primary_depart_date == date(2026, 8, 15)


@pytest.mark.asyncio
async def test_search_exact_one_call() -> None:
    calls = {"n": 0}

    class P:
        async def get_trip_quote(self, *a, **k):
            calls["n"] += 1
            return PriceQuote(price=10_000, currency="RUB", source="test")

        async def get_trip_band(self, *a, **k):
            return None

    await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["LED"],
        depart_date=date(2026, 9, 1),
        flexibility_days=0,
        today=date(2026, 8, 1),
    )
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_search_one_error_continues() -> None:
    class P:
        async def get_trip_quote(self, *a, **kwargs):
            d = kwargs.get("depart_date")
            if d == date(2026, 8, 15):
                raise RuntimeError("boom")
            return PriceQuote(price=11_000, currency="RUB", source="test")

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["LED"],
        depart_date=date(2026, 8, 15),
        flexibility_days=1,
        today=date(2026, 8, 1),
    )
    assert result is not None
    assert result.quote.price == 11_000


@pytest.mark.asyncio
async def test_search_all_empty_returns_none() -> None:
    class P:
        async def get_trip_quote(self, *a, **k):
            return None

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["LED"],
        depart_date=date(2026, 8, 15),
        flexibility_days=1,
        today=date(2026, 8, 1),
    )
    assert result is None


@pytest.mark.asyncio
async def test_round_trip_not_cartesian() -> None:
    seen: list[tuple] = []

    class P:
        async def get_trip_quote(self, *a, **kwargs):
            seen.append((kwargs.get("depart_date"), kwargs.get("return_date")))
            return PriceQuote(price=15_000, currency="RUB", source="test")

        async def get_trip_band(self, *a, **k):
            return None

    await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["AER"],
        depart_date=date(2026, 8, 15),
        return_date=date(2026, 8, 22),
        flexibility_days=3,
        today=date(2026, 8, 1),
    )
    assert len(seen) == 7
    for dep, ret in seen:
        assert (ret - dep).days == 7


@pytest.mark.asyncio
async def test_concurrency_limit(monkeypatch) -> None:
    active = {"n": 0, "max": 0}

    class P:
        async def get_trip_quote(self, *a, **k):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            await __import__("asyncio").sleep(0.01)
            active["n"] -= 1
            return PriceQuote(price=10_000, currency="RUB", source="test")

        async def get_trip_band(self, *a, **k):
            return None

    await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["LED"],
        depart_date=date(2026, 9, 10),
        flexibility_days=7,
        concurrency=3,
        today=date(2026, 8, 1),
    )
    assert active["max"] <= 3
