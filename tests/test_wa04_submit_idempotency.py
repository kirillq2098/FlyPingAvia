"""WA-04 hotfix: submit lock UX + Idempotency-Key + no dual CTA."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from flypingavia.db.models import Watch
from flypingavia.services.prices import PriceBand


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia/web/static"


def _band(cheap: float = 15_000) -> PriceBand:
    return PriceBand(
        cheap_max=cheap,
        typical=cheap * 1.25,
        expensive_min=cheap * 1.6,
        sample_size=8,
        currency="RUB",
        source="test",
    )


class _FixedBandProvider:
    def __init__(self, band: PriceBand | None):
        self._band = band

    async def search(self, **_kwargs):
        return None

    async def market_band(self, **_kwargs):
        return self._band


@pytest_asyncio.fixture
async def api_client(tmp_path, monkeypatch):
    db_path = tmp_path / "wa04_idem.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "555004")
    monkeypatch.setenv("BOT_TOKEN", "1:test")
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    # Reset engine between tests (module-level singleton).
    import flypingavia.db.session as sess

    sess._engine = None
    sess._session_factory = None

    from flypingavia.db.session import init_db

    await init_db()

    import flypingavia.api.app as api_mod
    from flypingavia.api.app import create_api

    monkeypatch.setattr(
        api_mod, "build_price_provider", lambda _s: _FixedBandProvider(_band())
    )
    app = create_api(get_settings())
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    if sess._engine is not None:
        await sess._engine.dispose()
    sess._engine = None
    sess._session_factory = None
    get_settings.cache_clear()


def test_version_stays_030() -> None:
    from flypingavia.version import __version__, FALLBACK_VERSION

    assert __version__ == "0.3.1"
    assert FALLBACK_VERSION == "0.3.1"


def test_frontend_single_cta_no_mainbutton_show() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="watch-submit"' in html
    assert "async function submitWatchForm(confirmLow)" in js
    assert "let isSubmitting = false" in js
    assert 'mb.setText("Создать подписку")' not in js
    assert "mb.onClick(state._mainBtnHandler)" not in js
    assert "Idempotency-Key" in js
    assert "shouldWarnLowThresholdLocal" in js
    assert "Создаём подписку…" in js
    assert "market_cheap_max" in js


def test_html_and_js_do_not_enable_mainbutton_together() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    # Не должно быть обработчика, показывающего MainButton как второй CTA.
    assert "mb.onClick(state._mainBtnHandler)" not in js
    assert 'mb.setText("Создать подписку")' not in js


@pytest.mark.asyncio
async def test_idempotency_key_returns_same_watch(api_client) -> None:
    payload = {
        "origin": "MOW",
        "destination": "LED",
        "max_price": 16_000,
        "depart_date": (date.today() + timedelta(days=14)).isoformat(),
        "confirm_low_threshold": True,
        "market_cheap_max": 15_000,
        "market_typical": 19_000,
    }
    headers = {"Idempotency-Key": "same-key-1"}
    r1 = await api_client.post("/api/watches", json=payload, headers=headers)
    r2 = await api_client.post("/api/watches", json=payload, headers=headers)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        watches = (await session.execute(select(Watch))).scalars().all()
        assert len(watches) == 1


@pytest.mark.asyncio
async def test_new_idempotency_key_allows_new_watch_after_window(api_client, monkeypatch) -> None:
    """Новый ключ после окна fingerprint может создать новую подписку."""
    from flypingavia.db import repository as repo

    payload = {
        "origin": "MOW",
        "destination": "AER",
        "max_price": 20_000,
        "confirm_low_threshold": True,
        "market_cheap_max": 18_000,
        "market_typical": 22_000,
    }
    r1 = await api_client.post(
        "/api/watches", json=payload, headers={"Idempotency-Key": "key-a"}
    )
    assert r1.status_code == 200

    # Имитация истечения short window: find_recent_similar всегда None.
    async def _none(*_a, **_k):
        return None

    monkeypatch.setattr(repo, "find_recent_similar_watch", _none)
    r2 = await api_client.post(
        "/api/watches", json=payload, headers={"Idempotency-Key": "key-b"}
    )
    assert r2.status_code == 200
    assert r2.json()["id"] != r1.json()["id"]


@pytest.mark.asyncio
async def test_parallel_same_idempotency_key_one_watch(api_client) -> None:
    # Прогрев пользователя, чтобы параллельные create не гонялись на INSERT users.
    me = await api_client.get("/api/me")
    assert me.status_code == 200

    payload = {
        "origin": "LED",
        "destination": "MOW",
        "max_price": 17_000,
        "confirm_low_threshold": True,
        "market_cheap_max": 15_000,
        "market_typical": 19_000,
    }
    headers = {"Idempotency-Key": "parallel-key"}

    async def _one():
        return await api_client.post("/api/watches", json=payload, headers=headers)

    results = await asyncio.gather(_one(), _one(), _one(), _one(), _one())
    assert all(r.status_code == 200 for r in results)
    ids = {r.json()["id"] for r in results}
    assert len(ids) == 1

    from flypingavia.db.session import session_scope

    async with session_scope() as session:
        watches = (await session.execute(select(Watch))).scalars().all()
        assert len(watches) == 1


@pytest.mark.asyncio
async def test_fingerprint_window_dedupes_without_key(api_client) -> None:
    payload = {
        "origin": "MOW",
        "destination": "KZN",
        "max_price": 12_000,
        "confirm_low_threshold": True,
        "market_cheap_max": 14_000,
        "market_typical": 18_000,
    }
    r1 = await api_client.post("/api/watches", json=payload)
    r2 = await api_client.post("/api/watches", json=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


@pytest.mark.asyncio
async def test_market_snapshot_skips_live_search(api_client, monkeypatch) -> None:
    import flypingavia.api.app as api_mod

    called = {"n": 0}

    async def _boom(*_a, **_k):
        called["n"] += 1
        raise RuntimeError("should not search")

    monkeypatch.setattr(api_mod, "search_flexible_trip", _boom)
    res = await api_client.post(
        "/api/watches",
        json={
            "origin": "MOW",
            "destination": "LED",
            "max_price": 16_000,
            "market_cheap_max": 15_000,
            "market_typical": 19_000,
        },
    )
    assert res.status_code == 200
    assert called["n"] == 0


@pytest.mark.asyncio
async def test_market_snapshot_warns_without_search(api_client, monkeypatch) -> None:
    import flypingavia.api.app as api_mod

    called = {"n": 0}

    async def _boom(*_a, **_k):
        called["n"] += 1
        raise RuntimeError("should not search")

    monkeypatch.setattr(api_mod, "search_flexible_trip", _boom)
    res = await api_client.post(
        "/api/watches",
        json={
            "origin": "MOW",
            "destination": "LED",
            "max_price": 10_000,
            "market_cheap_max": 15_000,
            "market_typical": 19_000,
        },
    )
    assert res.status_code == 409
    assert res.json()["detail"]["code"] == "LOW_THRESHOLD_CONFIRMATION_REQUIRED"
    assert called["n"] == 0


def test_frontend_local_warn_before_create() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    # Предупреждение локально до create; confirm вызывает submitWatchForm(true).
    assert "shouldWarnLowThresholdLocal(threshold)" in js
    assert "showLowThresholdWarn" in js
    idx_local = js.index("shouldWarnLowThresholdLocal")
    idx_create = js.index("await createWatch(threshold, !!confirmLow, key)")
    assert idx_local < idx_create
    assert "if (!confirmLow && shouldWarnLowThresholdLocal(threshold))" in js
