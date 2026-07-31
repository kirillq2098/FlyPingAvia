"""BUG-02: first Mini App login for a brand-new Telegram user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from flypingavia.api.telegram_auth import (
    TelegramAuthError,
    build_test_init_data,
    validate_telegram_init_data,
)
from flypingavia.config import Settings, get_settings
from flypingavia.db import models  # noqa: F401
from flypingavia.db.models import User
from flypingavia.db.session import get_session_factory, init_db

TOKEN = "bug02-test-bot-token-not-real"


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
async def bug02_db(tmp_path, monkeypatch):
    db_path = tmp_path / "bug02.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", TOKEN)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WEBAPP_URL", "https://app.flyping.ru")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", "3600")
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
async def test_first_login_creates_user_and_session(bug02_db) -> None:
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    tid = 880_000_001
    init = build_test_init_data(
        TOKEN,
        user_id=tid,
        username=None,
        first_name="Новый",
        auth_date=now_ts,
    )
    factory = get_session_factory()
    async with factory() as session:
        existing = await session.execute(select(User).where(User.telegram_id == tid))
        assert existing.scalar_one_or_none() is None

    app = create_api(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        me = await c.get("/api/me", headers=_auth(init))
        assert me.status_code == 200
        body = me.json()
        assert body["telegram_user_id"] == tid
        assert body["first_name"] == "Новый"
        assert body.get("username") in (None, "")

        watches = await c.get("/api/watches", headers=_auth(init))
        assert watches.status_code == 200
        assert watches.json() == []

        me2 = await c.get("/api/me", headers=_auth(init))
        assert me2.status_code == 200
        assert me2.json()["telegram_user_id"] == tid

    async with factory() as session:
        rows = (
            await session.execute(select(User).where(User.telegram_id == tid))
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].username is None


@pytest.mark.asyncio
async def test_first_login_without_last_name(bug02_db) -> None:
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    init = build_test_init_data(
        TOKEN,
        user_id=880_000_002,
        username="noname_ln",
        first_name="OnlyFirst",
        last_name=None,
        auth_date=now_ts,
    )
    app = create_api(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth(init))
    assert res.status_code == 200
    assert res.json()["telegram_user_id"] == 880_000_002


@pytest.mark.asyncio
async def test_invalid_signature_rejected(bug02_db) -> None:
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    init = build_test_init_data(TOKEN, user_id=880_000_003, auth_date=now_ts)
    bad = init[:-8] + "deadbeef"
    app = create_api(_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth(bad))
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "INVALID_HASH"
    assert TOKEN not in res.text


@pytest.mark.asyncio
async def test_expired_initdata_rejected(bug02_db) -> None:
    from flypingavia.api.app import create_api

    old = int((datetime.now(timezone.utc) - timedelta(hours=3)).timestamp())
    init = build_test_init_data(TOKEN, user_id=880_000_004, auth_date=old)
    app = create_api(_settings(telegram_init_data_max_age_seconds=3600))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth(init))
    assert res.status_code == 401
    assert res.json()["detail"]["code"] == "EXPIRED_INIT_DATA"


def test_validate_user_without_username_still_signed() -> None:
    now_ts = int(datetime.now(timezone.utc).timestamp())
    init = build_test_init_data(
        TOKEN, user_id=42, username=None, first_name="X", auth_date=now_ts
    )
    user = validate_telegram_init_data(init, bot_token=TOKEN, max_age_seconds=3600)
    assert user.id == 42
    assert user.username is None
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(init + "x", bot_token=TOKEN, max_age_seconds=3600)
    assert ei.value.code == "INVALID_HASH"


def test_frontend_bug02_hash_fallback_and_retry() -> None:
    root = Path(__file__).resolve().parents[1]
    js = (root / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    lp = (root / "flypingavia/web/static/launch-params.js").read_text(encoding="utf-8")
    html = (root / "flypingavia/web/static/index.html").read_text(encoding="utf-8")

    assert "readInitDataFromLocationHash" in js
    assert "tgWebAppData" in lp
    assert "FlyPingLaunchParams" in lp
    assert "signalTelegramReady" in js
    assert "waitForInitData(12000)" in js
    assert "manualRetry" in js
    assert "cachedInitData" in js
    assert "auth-retry" in html
    assert "Повторить" in html
    assert "auth-locked" in html
    assert "Не удалось получить данные запуска Telegram" in js
    assert '"tma "' in js
    assert "localStorage.setItem" not in js
    assert "launch-params.js" in html
