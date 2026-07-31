"""BUG-02.1: session must survive beyond the old ~10s wait+retry window."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from flypingavia.api.telegram_auth import build_test_init_data
from flypingavia.config import Settings, get_settings
from flypingavia.db import models  # noqa: F401
from flypingavia.db.models import User
from flypingavia.db.session import get_session_factory, init_db

TOKEN = "bug021-test-bot-token-not-real"


def _auth(init_data: str) -> dict[str, str]:
    return {"Authorization": f"tma {init_data}"}


def _settings(**kwargs) -> Settings:
    base = {
        "bot_token": TOKEN,
        "app_env": "production",
        "webapp_url": "https://app.flyping.ru",
        "travelpayouts_token": "tok",
        "webapp_dev_user_id": 0,
        "telegram_init_data_max_age_seconds": 3600,
    }
    base.update(kwargs)
    return Settings(**base)


@pytest.fixture
async def bug021_db(tmp_path, monkeypatch):
    db_path = tmp_path / "bug021.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", TOKEN)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WEBAPP_URL", "https://app.flyping.ru")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    get_settings.cache_clear()
    import flypingavia.db.session as sess

    sess._engine = None
    sess._session_factory = None
    await init_db()
    yield
    if sess._engine is not None:
        await sess._engine.dispose()
    sess._engine = None
    sess._session_factory = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_session_survives_30s_with_repeated_me(bug021_db) -> None:
    """Model: delayed first login + activity past the old 10s false-failure window."""
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    tid = 881_000_001
    # Simulate late initData becoming available (already signed for "now").
    await asyncio.sleep(0.05)
    init = build_test_init_data(
        TOKEN,
        user_id=tid,
        username=None,
        first_name="Android",
        auth_date=now_ts,
    )
    app = create_api(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        me1 = await c.get("/api/me", headers=_auth(init))
        assert me1.status_code == 200
        assert me1.json()["telegram_user_id"] == tid

        # Stay "open" past the previous 5s+5s bootstrap failure window.
        await asyncio.sleep(0.2)
        for _ in range(3):
            me = await c.get("/api/me", headers=_auth(init))
            assert me.status_code == 200
            watches = await c.get("/api/watches", headers=_auth(init))
            assert watches.status_code == 200

        # Duplicate bootstrap-equivalent /api/me must not break.
        me2 = await c.get("/api/me", headers=_auth(init))
        assert me2.status_code == 200

    factory = get_session_factory()
    async with factory() as session:
        rows = (
            await session.execute(select(User).where(User.telegram_id == tid))
        ).scalars().all()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_diag_endpoint_safe(bug021_db) -> None:
    from flypingavia.api.app import create_api

    app = create_api(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.post(
            "/api/diag/miniapp-bootstrap",
            json={
                "stage": "missing_init_data",
                "has_init_data": False,
                "init_data_len": 0,
                "elapsed_ms": 10400,
                "inside_telegram": True,
            },
        )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert TOKEN not in res.text


def test_frontend_bug021_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    js = (root / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    html = (root / "flypingavia/web/static/index.html").read_text(encoding="utf-8")

    assert 'class="auth-locked"' in html or "auth-locked" in html.split("<body", 1)[1][:80]
    assert "Загрузка FlyPing" in html
    assert "cachedInitData" in js
    assert "rememberInitData" in js
    assert "readInitDataFromTelegramStorage" in js
    assert "armLateInitDataResume" in js
    assert "waitForInitData(12000)" in js
    assert "reportDiag" in js
    assert "/api/diag/miniapp-bootstrap" in js
    assert "hashchange" in js
    # Old stacked 5s+5s auto-retry must be gone (that produced the ~10s false session).
    assert "waitForInitData(5000)" not in js
    assert "isRetry" not in js
    assert '"tma "' in js
    # BUG-02.2: no UA-only "inside Telegram"; distinguish launch-data vs session.
    assert "isTelegramMiniAppContext" in js
    assert "/Telegram/i" not in js
    assert "Не удалось получить данные запуска Telegram" in js
    assert "/Telegram/i" not in js
    assert "0.3.0-bug023" in html
    assert "launch-params.js" in html
    assert "FlyPingLaunchParams" in (root / "flypingavia/web/static/launch-params.js").read_text(
        encoding="utf-8"
    )
