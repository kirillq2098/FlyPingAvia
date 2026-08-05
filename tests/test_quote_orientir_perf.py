"""Quote orientir: cache, SWR, concurrency, UI copy, timeouts."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from flypingavia.services.prices import PriceBand, PriceQuote
from flypingavia.services.provider_http_cache import ProviderHttpCache
from flypingavia.services.quote_cache import (
    QuoteCache,
    make_quote_cache_key,
)
from flypingavia.services.flexible_dates import search_flexible_trip
from flypingavia.version import FALLBACK_VERSION, __version__

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia/web/static"


def test_version_stays_030() -> None:
    assert __version__ == "0.3.1"
    assert FALLBACK_VERSION == "0.3.1"


def test_ui_has_orientir_not_vilka() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    blob = html + "\n" + js
    assert "вилка" not in blob.lower()
    assert "Ориентир по стоимости" in blob
    assert "Выгодная цена" in js
    assert "Средняя цена" in js
    assert "Высокая цена" in js
    assert "Анализируем стоимость билетов…" in js
    assert "async function requestQuote" in js
    assert "quoteAbort" in js
    assert "scheduleQuoteRefresh" in js


def test_cache_key_normalized() -> None:
    a = make_quote_cache_key(
        origin="mow",
        destination="ovb",
        origin_search="dme,svo,mow",
        destination_search="ovb",
        depart_date=date(2026, 11, 27),
        return_date=date(2026, 12, 4),
        flexibility_days=7,
        adults=1,
        children=0,
        infants=0,
        currency="rub",
        trip_type="round",
        provider="Travelpayouts",
    )
    b = make_quote_cache_key(
        origin="MOW",
        destination="OVB",
        origin_search="MOW,SVO,DME",
        destination_search="OVB",
        depart_date=date(2026, 11, 27),
        return_date=date(2026, 12, 4),
        flexibility_days=7,
        adults=1,
        children=0,
        infants=0,
        currency="RUB",
        trip_type="round",
        provider="travelpayouts",
    )
    assert a == b


def test_provider_http_cache_hit_miss() -> None:
    cache = ProviderHttpCache(ttl_seconds=60)
    key = cache.make_key("https://example.test/x", {"origin": "MOW", "token": "SECRET"})
    assert "SECRET" not in key
    assert cache.get(key) is None
    cache.set(key, {"data": [1]})
    assert cache.get(key) == {"data": [1]}
    assert cache.hits == 1
    assert cache.misses == 1


def test_quote_cache_fresh_stale() -> None:
    cache = QuoteCache(fresh_ttl=1, stale_ttl=10)
    key = "k1"
    cache.store(key, {"price": 100})
    entry, status = cache.lookup(key)
    assert status == "fresh"
    assert entry is not None
    entry.created_at -= 2
    entry2, status2 = cache.lookup(key)
    assert status2 == "stale"
    entry2.created_at -= 20
    entry3, status3 = cache.lookup(key)
    assert status3 == "miss"
    assert entry3 is None


@pytest.mark.asyncio
async def test_quote_cache_coalesce_single_flight() -> None:
    cache = QuoteCache()
    calls = {"n": 0}

    async def factory():
        calls["n"] += 1
        await asyncio.sleep(0.05)
        return {"price": 42}

    results = await asyncio.gather(
        cache.coalesce("same", factory),
        cache.coalesce("same", factory),
        cache.coalesce("same", factory),
    )
    assert calls["n"] == 1
    assert all(r["price"] == 42 for r in results)


@pytest.mark.asyncio
async def test_flexible_concurrency_limit() -> None:
    active = {"n": 0, "max": 0}

    class P:
        async def get_trip_quote(self, *a, **k):
            active["n"] += 1
            active["max"] = max(active["max"], active["n"])
            await asyncio.sleep(0.02)
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
        concurrency=4,
        soft_timeout_seconds=None,
        hard_timeout_seconds=None,
        today=date(2026, 8, 1),
    )
    assert active["max"] <= 4


@pytest.mark.asyncio
async def test_flexible_soft_timeout_partial() -> None:
    started = {"n": 0}

    class P:
        async def get_trip_quote(self, *a, **kwargs):
            started["n"] += 1
            d = kwargs.get("depart_date")
            # Primary (offset 0) is 2026-09-10
            if d == date(2026, 9, 10):
                await asyncio.sleep(0.01)
                return PriceQuote(price=15_000, currency="RUB", source="test")
            await asyncio.sleep(0.5)
            return PriceQuote(price=12_000, currency="RUB", source="test")

        async def get_trip_band(self, *a, **k):
            return None

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["LED"],
        depart_date=date(2026, 9, 10),
        flexibility_days=3,
        concurrency=2,
        soft_timeout_seconds=0.05,
        hard_timeout_seconds=2.0,
        today=date(2026, 8, 1),
    )
    assert result is not None
    assert result.partial is True
    assert result.completed_count >= 1
    assert result.completed_count < result.combinations_count


@pytest.mark.asyncio
async def test_flexible_band_from_samples() -> None:
    class P:
        async def get_trip_quote(self, *a, **kwargs):
            d = kwargs.get("depart_date")
            prices = {
                date(2026, 8, 14): 20_000,
                date(2026, 8, 15): 18_000,
                date(2026, 8, 16): 12_000,
            }
            return PriceQuote(
                price=prices[d], currency="RUB", source="test", origin_code="MOW", destination_code="AER"
            )

        async def get_trip_band(self, *a, **k):
            raise RuntimeError("should use samples")

    result = await search_flexible_trip(
        P(),  # type: ignore[arg-type]
        origins=["MOW"],
        destinations=["AER"],
        depart_date=date(2026, 8, 15),
        flexibility_days=1,
        soft_timeout_seconds=None,
        hard_timeout_seconds=None,
        today=date(2026, 8, 1),
    )
    assert result is not None
    assert result.band is not None
    assert result.band.sample_size == 3
    assert result.quote.price == 12_000


@pytest_asyncio.fixture
async def quote_api(tmp_path, monkeypatch):
    db_path = tmp_path / "quote.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "555010")
    monkeypatch.setenv("BOT_TOKEN", "1:test")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")

    from flypingavia.config import get_settings
    import flypingavia.db.session as sess
    from flypingavia.services.quote_cache import default_quote_cache
    from flypingavia.services.provider_http_cache import default_provider_http_cache

    get_settings.cache_clear()
    sess._engine = None
    sess._session_factory = None
    default_quote_cache.clear()
    default_provider_http_cache.clear()

    from flypingavia.db.session import init_db

    await init_db()

    import flypingavia.api.app as api_mod
    from flypingavia.api.app import create_api

    class FixedProvider:
        def __init__(self):
            self.calls = 0

        async def get_trip_quote(self, *a, **k):
            self.calls += 1
            await asyncio.sleep(0.01)
            return PriceQuote(
                price=18_000,
                currency="RUB",
                source="test",
                origin_code="MOW",
                destination_code="OVB",
            )

        async def get_trip_band(self, *a, **k):
            self.calls += 1
            return PriceBand(
                cheap_max=15_000,
                typical=18_000,
                expensive_min=24_000,
                sample_size=5,
                currency="RUB",
                source="test",
            )

        async def get_cheapest_across(self, *a, **k):
            return await self.get_trip_quote()

        async def get_price_band_across(self, *a, **k):
            return await self.get_trip_band()

    provider = FixedProvider()

    async def _search(provider_arg, **kwargs):
        # Use real search_flexible_trip against FixedProvider methods
        from flypingavia.services import flexible_dates as fd

        return await fd.search_flexible_trip(provider, **kwargs)

    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: provider)
    monkeypatch.setattr(api_mod, "search_flexible_trip", _search)

    app = create_api(get_settings())
    # Replace closed-over provider used by create_api — search_flexible_trip patched above.
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, provider

    if sess._engine is not None:
        await sess._engine.dispose()
    sess._engine = None
    sess._session_factory = None
    default_quote_cache.clear()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_api_quote_cache_hit_skips_provider(quote_api) -> None:
    client, provider = quote_api
    params = {
        "origin": "MOW",
        "destination": "OVB",
        "depart_date": (date.today() + timedelta(days=40)).isoformat(),
        "flexibility_days": 0,
    }
    r1 = await client.get("/api/quote", params=params)
    assert r1.status_code == 200
    body1 = r1.json()
    assert body1["cheap_max"] == 15_000
    assert body1["title"] == "Ориентир по стоимости"
    calls_after_first = provider.calls

    r2 = await client.get("/api/quote", params=params)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["cached"] is True
    assert body2["stale"] is False
    assert provider.calls == calls_after_first

    metrics = await client.get("/api/metrics/quote")
    assert metrics.status_code == 200
    assert metrics.json()["metrics"]["quote_cache_hits"] >= 1


@pytest.mark.asyncio
async def test_api_quote_stale_then_refresh(quote_api, monkeypatch) -> None:
    from flypingavia.services.quote_cache import default_quote_cache

    client, provider = quote_api
    params = {
        "origin": "LED",
        "destination": "MOW",
        "depart_date": (date.today() + timedelta(days=50)).isoformat(),
        "flexibility_days": 0,
    }
    r1 = await client.get("/api/quote", params=params)
    assert r1.status_code == 200
    # Force stale
    key = next(iter(default_quote_cache._store.keys()))
    default_quote_cache._store[key].created_at -= default_quote_cache.fresh_ttl + 1
    calls = provider.calls
    r2 = await client.get("/api/quote", params=params)
    assert r2.status_code == 200
    assert r2.json()["stale"] is True
    assert r2.json()["refreshing"] is True
    assert provider.calls == calls  # no provider on stale serve

    r3 = await client.get("/api/quote", params={**params, "refresh": "true"})
    assert r3.status_code == 200
    assert r3.json()["stale"] is False
    assert provider.calls > calls


@pytest.mark.asyncio
async def test_create_still_skips_search_with_snapshot(quote_api, monkeypatch) -> None:
    client, _provider = quote_api
    import flypingavia.api.app as api_mod

    called = {"n": 0}

    async def boom(*a, **k):
        called["n"] += 1
        raise RuntimeError("no search")

    monkeypatch.setattr(api_mod, "search_flexible_trip", boom)
    res = await client.post(
        "/api/watches",
        json={
            "origin": "MOW",
            "destination": "OVB",
            "max_price": 16_000,
            "market_cheap_max": 15_000,
            "market_typical": 18_000,
            "confirm_low_threshold": False,
        },
    )
    assert res.status_code == 200
    assert called["n"] == 0


def test_frontend_create_uses_snapshot_not_quote_search() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "market_cheap_max" in js
    assert "shouldWarnLowThresholdLocal" in js
    create_idx = js.index("async function createWatch")
    end = js.index("function newIdempotencyKey", create_idx)
    slice_ = js[create_idx:end]
    assert "/api/watches" in slice_
    assert "/api/quote" not in slice_
