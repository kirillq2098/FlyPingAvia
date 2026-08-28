"""P0: exact-date price integrity — regression for MOW→IST wrong-month fallback."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from flypingavia.services.flexible_dates import search_flexible_trip
from flypingavia.services.price_date_guard import quote_departure_matches_watch
from flypingavia.services.prices import PriceQuote, TravelpayoutsPriceProvider

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia/web/static"

TARGET = date(2027, 1, 3)
MOW_IST_FIXTURE = {
    "MOW": [
        {"value": 11266, "depart_date": "2027-01-14", "number_of_changes": 0, "actual": True},
    ],
    "VKO": [
        {"value": 11266, "depart_date": "2027-01-14", "number_of_changes": 0, "actual": True},
    ],
    "SVO": [
        {"value": 25701, "depart_date": "2027-01-03", "number_of_changes": 0, "actual": True},
    ],
    "DME": [
        {"value": 27288, "depart_date": "2027-01-03", "number_of_changes": 1, "actual": True},
    ],
    "ZIA": [
        {"value": 35330, "depart_date": "2027-01-03", "number_of_changes": 1, "actual": True},
    ],
}


def _matrix_payload(origin: str) -> dict:
    return {"data": list(MOW_IST_FIXTURE.get(origin.upper(), []))}


@pytest.fixture
def mow_ist_provider() -> TravelpayoutsPriceProvider:
    provider = TravelpayoutsPriceProvider("test-token")

    async def fake_matrix(origin: str, destination: str, currency: str, month: date):
        assert destination.upper() == "IST"
        return list(MOW_IST_FIXTURE.get(origin.upper(), []))

    async def fake_calendar(url: str, params: dict):
        return {"data": {}}

    provider._month_matrix_items = fake_matrix  # type: ignore[method-assign]
    provider._get_json = AsyncMock(side_effect=fake_calendar)  # type: ignore[method-assign]
    return provider


# --- EXACT DATE ---


@pytest.mark.asyncio
async def test_exact_candidate_selected(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    quote = await mow_ist_provider.get_cheapest("SVO", "IST", TARGET)
    assert quote is not None
    assert int(quote.price) == 25701
    assert quote.depart_date == TARGET
    assert quote.transfers == 0


@pytest.mark.asyncio
async def test_cheaper_wrong_date_rejected(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    quote = await mow_ist_provider.get_cheapest("MOW", "IST", TARGET)
    assert quote is None


@pytest.mark.asyncio
async def test_month_minimum_rejected_for_flex_zero(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    quote = await mow_ist_provider.get_cheapest("VKO", "IST", TARGET)
    assert quote is None


@pytest.mark.asyncio
async def test_city_level_wrong_date_rejected(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    quote = await mow_ist_provider.get_cheapest("MOW", "IST", TARGET)
    assert quote is None


@pytest.mark.asyncio
async def test_airport_exact_wins_across(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    codes = ["MOW", "SVO", "DME", "VKO", "ZIA"]
    quote = await mow_ist_provider.get_cheapest_across(codes, ["IST"], TARGET)
    assert quote is not None
    assert quote.origin_code == "SVO"
    assert int(quote.price) == 25701
    assert quote.depart_date == TARGET


@pytest.mark.asyncio
async def test_no_exact_candidate_returns_none(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    quote = await mow_ist_provider.get_cheapest_across(["MOW", "VKO"], ["IST"], TARGET)
    assert quote is None


# --- DATE PROPAGATION ---


@pytest.mark.asyncio
async def test_found_depart_date_from_quote_flex_zero() -> None:
    class P:
        async def get_trip_quote(self, origins, destinations, **kwargs):
            d = kwargs.get("depart_date")
            if d != TARGET:
                return None
            return PriceQuote(
                price=25_701,
                currency="RUB",
                source="test",
                origin_code="SVO",
                destination_code="IST",
                depart_date=TARGET,
            )

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW", "SVO"],
        destinations=["IST"],
        depart_date=TARGET,
        flexibility_days=0,
    )
    assert result is not None
    assert result.found_depart_date == TARGET
    assert result.quote.depart_date == TARGET


@pytest.mark.asyncio
async def test_flex_zero_found_equals_requested() -> None:
    class P:
        async def get_trip_quote(self, *a, **kwargs):
            return PriceQuote(
                price=20_000,
                currency="RUB",
                source="test",
                depart_date=kwargs.get("depart_date"),
            )

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["IST"],
        depart_date=TARGET,
        flexibility_days=0,
    )
    assert result is not None
    assert result.found_depart_date == TARGET


# --- FLEX ---


@pytest.mark.parametrize(
    ("offset", "expected_ok"),
    [(3, True), (-3, True), (4, False), (-4, False)],
)
def test_flex_window_guard(offset: int, expected_ok: bool) -> None:
    primary = date(2027, 1, 10)
    candidate = primary.replace(day=primary.day + offset)
    ok, _ = quote_departure_matches_watch(
        watch_depart_date=primary,
        candidate_depart_date=candidate,
        flexibility_days=3,
        today=date(2027, 1, 1),
    )
    assert ok is expected_ok


@pytest.mark.asyncio
async def test_flex_preserves_actual_candidate_date() -> None:
    prices = {
        date(2027, 1, 5): 30_000,
        date(2027, 1, 6): 11_266,
    }

    class P:
        async def get_trip_quote(self, *a, **kwargs):
            d = kwargs.get("depart_date")
            if d not in prices:
                return None
            return PriceQuote(
                price=prices[d],
                currency="RUB",
                source="test",
                depart_date=d,
            )

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["IST"],
        depart_date=TARGET,
        flexibility_days=3,
        today=date(2027, 1, 1),
    )
    assert result is not None
    assert result.found_depart_date == date(2027, 1, 6)
    assert result.quote.depart_date == date(2027, 1, 6)


@pytest.mark.asyncio
async def test_flex_rejects_arbitrary_month_minimum_outside_window() -> None:
    class P:
        async def get_trip_quote(self, *a, **kwargs):
            d = kwargs.get("depart_date")
            if d == date(2027, 1, 25):
                return PriceQuote(price=9_000, currency="RUB", source="test", depart_date=d)
            return None

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["IST"],
        depart_date=TARGET,
        flexibility_days=3,
        today=date(2027, 1, 1),
    )
    assert result is None


# --- NO DATE ---


@pytest.mark.asyncio
async def test_no_date_watch_uses_latest_path() -> None:
    provider = TravelpayoutsPriceProvider("tok")

    async def fake_latest(url: str, params: dict):
        return {"data": [{"value": 15_000, "number_of_changes": 0}]}

    provider._get_json = AsyncMock(side_effect=fake_latest)  # type: ignore[method-assign]
    quote = await provider.get_cheapest("MOW", "IST", None)
    assert quote is not None
    assert int(quote.price) == 15_000
    assert quote.depart_date is None


# --- CHECKER GUARD ---


def test_exact_date_wrong_candidate_cannot_alert() -> None:
    ok, reason = quote_departure_matches_watch(
        watch_depart_date=TARGET,
        candidate_depart_date=date(2027, 1, 14),
        flexibility_days=0,
    )
    assert not ok
    assert reason == "wrong_departure_date"


def test_exact_date_valid_candidate_can_alert() -> None:
    ok, reason = quote_departure_matches_watch(
        watch_depart_date=TARGET,
        candidate_depart_date=TARGET,
        flexibility_days=0,
    )
    assert ok
    assert reason == "exact_match"


def test_flexible_inside_window_can_alert() -> None:
    ok, _ = quote_departure_matches_watch(
        watch_depart_date=TARGET,
        candidate_depart_date=date(2027, 1, 5),
        flexibility_days=3,
        today=date(2027, 1, 1),
    )
    assert ok


def test_flexible_outside_window_cannot_alert() -> None:
    ok, reason = quote_departure_matches_watch(
        watch_depart_date=TARGET,
        candidate_depart_date=date(2027, 1, 14),
        flexibility_days=3,
        today=date(2027, 1, 1),
    )
    assert not ok
    assert reason == "outside_flex_window"


def test_no_date_watch_guard_allows_any() -> None:
    ok, reason = quote_departure_matches_watch(
        watch_depart_date=None,
        candidate_depart_date=date(2027, 1, 14),
        flexibility_days=0,
    )
    assert ok
    assert reason == "no_watch_date"


# --- UI ---


def test_ui_aviasales_attribution() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "По данным Travelpayouts" not in js
    assert "По данным Aviasales" in js
    assert "Фактическая цена на Aviasales может отличаться" in js


def test_no_exact_quote_state_renders() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "renderNoExactPriceState" in js
    assert "no_exact_price" in js
    assert "Пока нет данных о цене на эту дату" in js


def test_threshold_ux_unchanged() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "При какой цене сообщить?" in (ROOT / "flypingavia/web/static/index.html").read_text(
        encoding="utf-8"
    )
    assert '<div class="band-row cheap">' not in js
    assert 'thresholdInput.value = ""' in js or 'thr.value = ""' in js


def test_cache_buster_updated() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "0.3.1-exactdate1" in html
    assert "0.3.0-thresholdfix1" not in html


# --- MOW IST REGRESSION ---


@pytest.mark.asyncio
async def test_mow_ist_regression_jan_3_2027(mow_ist_provider: TravelpayoutsPriceProvider) -> None:
    result = await search_flexible_trip(
        mow_ist_provider,
        origins=["MOW", "SVO", "DME", "VKO", "ZIA"],
        destinations=["IST"],
        depart_date=TARGET,
        flexibility_days=0,
    )
    assert result is not None
    assert result.quote.origin_code == "SVO"
    assert int(result.quote.price) == 25701
    assert result.quote.depart_date == TARGET
    assert result.found_depart_date == TARGET
