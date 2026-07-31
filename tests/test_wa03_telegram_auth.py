"""WA-03: Telegram Mini App initData auth, APP_ENV, isolation, frontend contract."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, quote

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from flypingavia.api.telegram_auth import (
    FUTURE_AUTH_SKEW_SECONDS,
    MAX_INIT_DATA_LENGTH,
    MAX_INIT_DATA_PARAMS,
    TelegramAuthError,
    TelegramWebAppUser,
    build_test_init_data,
    validate_telegram_init_data,
)
from flypingavia.config import Settings, get_settings


TOKEN = "123456:WA03TOKEN"
FIXED_NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)
FIXED_TS = int(FIXED_NOW.timestamp())


def _auth_header(init_data: str) -> dict[str, str]:
    return {"Authorization": f"tma {init_data}"}


def _settings(**kwargs) -> Settings:
    base = {
        "bot_token": TOKEN,
        "app_env": "test",
        "webapp_dev_user_id": 0,
        "travelpayouts_token": "",
        "telegram_init_data_max_age_seconds": 3600,
    }
    base.update(kwargs)
    return Settings(**base)


def _sign(payload: dict[str, str], bot_token: str = TOKEN) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    payload = dict(payload)
    payload["hash"] = hmac.new(
        secret_key, data_check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in payload.items())


def _user_json(user_id: int = 42, first_name: str = "Кирилл", username: str = "kirill") -> str:
    return json.dumps(
        {"id": user_id, "first_name": first_name, "username": username},
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _valid_init(
    *,
    user_id: int = 42,
    auth_date: int | None = None,
    first_name: str = "Кирилл",
    username: str = "kirill",
    extra: dict[str, str] | None = None,
) -> str:
    return build_test_init_data(
        TOKEN,
        user_id=user_id,
        username=username,
        first_name=first_name,
        auth_date=FIXED_TS if auth_date is None else auth_date,
        extra=extra,
    )


# --- crypto validation ---


def test_valid_hash_accepted() -> None:
    init = _valid_init()
    user = validate_telegram_init_data(
        init, bot_token=TOKEN, max_age_seconds=3600, now=FIXED_NOW
    )
    assert user.id == 42
    assert user.first_name == "Кирилл"
    assert user.username == "kirill"


def test_bad_hash_rejected() -> None:
    init = _valid_init() + "x"
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(init, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_HASH"


def test_tampered_user_rejected() -> None:
    init = _valid_init()
    pairs = dict(parse_qsl(init, keep_blank_values=True))
    user_obj = json.loads(pairs["user"])
    user_obj["id"] = 99
    pairs["user"] = json.dumps(user_obj, separators=(",", ":"), ensure_ascii=False)
    bad = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in pairs.items())
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(bad, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_HASH"


def test_tampered_auth_date_rejected() -> None:
    init = _valid_init()
    bad = init.replace(f"auth_date={FIXED_TS}", f"auth_date={FIXED_TS - 10}")
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(bad, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_HASH"


def test_missing_hash() -> None:
    payload = {"auth_date": str(FIXED_TS), "user": _user_json()}
    raw = "&".join(f"{k}={quote(v, safe='')}" for k, v in payload.items())
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_HASH"


def test_duplicate_hash_rejected() -> None:
    init = _valid_init()
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(init + "&hash=abc", bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_HASH"


def test_missing_auth_date() -> None:
    payload = {"user": _user_json(), "query_id": "q"}
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code in {"EXPIRED_INIT_DATA", "INVALID_INIT_DATA"}


def test_non_numeric_auth_date() -> None:
    payload = {"auth_date": "yesterday", "user": _user_json()}
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code in {"EXPIRED_INIT_DATA", "INVALID_INIT_DATA"}


def test_expired_auth_date() -> None:
    init = _valid_init(auth_date=FIXED_TS - 7200)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(
            init, bot_token=TOKEN, max_age_seconds=3600, now=FIXED_NOW
        )
    assert ei.value.code == "EXPIRED_INIT_DATA"


def test_auth_date_within_future_skew_ok() -> None:
    init = _valid_init(auth_date=FIXED_TS + FUTURE_AUTH_SKEW_SECONDS)
    user = validate_telegram_init_data(
        init, bot_token=TOKEN, max_age_seconds=3600, now=FIXED_NOW
    )
    assert user.id == 42


def test_auth_date_too_far_future() -> None:
    init = _valid_init(auth_date=FIXED_TS + FUTURE_AUTH_SKEW_SECONDS + 1)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(init, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "FUTURE_AUTH_DATE"


def test_missing_user() -> None:
    payload = {"auth_date": str(FIXED_TS), "query_id": "q"}
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_TELEGRAM_USER"


def test_broken_user_json() -> None:
    payload = {"auth_date": str(FIXED_TS), "user": "{not-json"}
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_TELEGRAM_USER"


def test_missing_user_id() -> None:
    payload = {
        "auth_date": str(FIXED_TS),
        "user": json.dumps({"username": "x"}, separators=(",", ":")),
    }
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_TELEGRAM_USER"


def test_negative_user_id() -> None:
    payload = {
        "auth_date": str(FIXED_TS),
        "user": json.dumps({"id": -1}, separators=(",", ":")),
    }
    raw = _sign(payload)
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data(raw, bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_TELEGRAM_USER"


def test_empty_init_data() -> None:
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data("", bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "MISSING_INIT_DATA"


def test_too_long_init_data() -> None:
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data("a" * (MAX_INIT_DATA_LENGTH + 1), bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_INIT_DATA"


def test_too_many_params() -> None:
    parts = [f"k{i}=v{i}" for i in range(MAX_INIT_DATA_PARAMS + 1)]
    with pytest.raises(TelegramAuthError) as ei:
        validate_telegram_init_data("&".join(parts), bot_token=TOKEN, now=FIXED_NOW)
    assert ei.value.code == "INVALID_INIT_DATA"


def test_param_order_does_not_matter() -> None:
    user = _user_json()
    a = _sign({"auth_date": str(FIXED_TS), "user": user, "query_id": "AA"})
    b = _sign({"query_id": "AA", "user": user, "auth_date": str(FIXED_TS)})
    ua = validate_telegram_init_data(a, bot_token=TOKEN, now=FIXED_NOW)
    ub = validate_telegram_init_data(b, bot_token=TOKEN, now=FIXED_NOW)
    assert ua.id == ub.id == 42


def test_unicode_name_ok() -> None:
    init = _valid_init(first_name="Сергей")
    user = validate_telegram_init_data(init, bot_token=TOKEN, now=FIXED_NOW)
    assert user.first_name == "Сергей"


def test_compare_digest_used() -> None:
    src = Path("flypingavia/api/telegram_auth.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in src


def test_query_id_optional() -> None:
    init = build_test_init_data(
        TOKEN, user_id=7, auth_date=FIXED_TS, include_query_id=False
    )
    user = validate_telegram_init_data(init, bot_token=TOKEN, now=FIXED_NOW)
    assert user.id == 7


def test_max_age_setting_gt_zero() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(telegram_init_data_max_age_seconds=0)


@pytest.fixture
async def wa03_db(tmp_path, monkeypatch):
    db_path = tmp_path / "wa03.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", "3600")
    monkeypatch.setenv("APP_ENV", "test")

    import flypingavia.db.session as db_session

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None

    from flypingavia.db.session import init_db

    await init_db()
    yield
    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


def _prod_settings(**kwargs) -> Settings:
    base = {
        "app_env": "production",
        "webapp_url": "https://app.example.com",
        "travelpayouts_token": "tok",
        "webapp_dev_user_id": 0,
    }
    base.update(kwargs)
    return _settings(**base)


@pytest.mark.asyncio
async def test_production_without_header_401(wa03_db) -> None:
    from flypingavia.api.app import create_api

    app = create_api(_prod_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me")
    assert res.status_code == 401
    body = res.json()["detail"]
    assert body["code"] == "MISSING_INIT_DATA"
    assert TOKEN not in res.text


@pytest.mark.asyncio
async def test_production_valid_initdata_ok(wa03_db) -> None:
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    init = build_test_init_data(TOKEN, user_id=101, auth_date=now_ts, first_name="A")
    app = create_api(_prod_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth_header(init))
    assert res.status_code == 200
    assert res.json()["telegram_user_id"] == 101


@pytest.mark.asyncio
async def test_production_bad_initdata_401(wa03_db) -> None:
    from flypingavia.api.app import create_api

    app = create_api(_prod_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth_header("auth_date=1&user={}&hash=00"))
    assert res.status_code == 401
    assert res.json()["detail"]["code"] in {
        "INVALID_HASH",
        "INVALID_TELEGRAM_USER",
        "INVALID_INIT_DATA",
        "EXPIRED_INIT_DATA",
    }


@pytest.mark.asyncio
async def test_production_never_uses_dev_user(wa03_db) -> None:
    with pytest.raises((ValidationError, ValueError)):
        _prod_settings(webapp_dev_user_id=999)


@pytest.mark.asyncio
async def test_development_uses_dev_user(wa03_db) -> None:
    from flypingavia.api.app import create_api

    s = _settings(app_env="development", webapp_dev_user_id=555001)
    app = create_api(s)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me")
    assert res.status_code == 200
    assert res.json()["telegram_user_id"] == 555001


@pytest.mark.asyncio
async def test_development_valid_initdata_overrides_dev(wa03_db) -> None:
    from flypingavia.api.app import create_api

    now_ts = int(datetime.now(timezone.utc).timestamp())
    init = build_test_init_data(TOKEN, user_id=777, auth_date=now_ts)
    s = _settings(app_env="development", webapp_dev_user_id=555001)
    app = create_api(s)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth_header(init))
    assert res.status_code == 200
    assert res.json()["telegram_user_id"] == 777


@pytest.mark.asyncio
async def test_development_bad_initdata_no_fallback(wa03_db) -> None:
    from flypingavia.api.app import create_api

    s = _settings(app_env="development", webapp_dev_user_id=555001)
    app = create_api(s)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me", headers=_auth_header("broken"))
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_development_no_init_no_dev_401(wa03_db) -> None:
    from flypingavia.api.app import create_api

    s = _settings(app_env="development", webapp_dev_user_id=0)
    app = create_api(s)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_dependency_override(wa03_db) -> None:
    from flypingavia.api.app import create_api

    app = create_api(_settings(app_env="test", webapp_dev_user_id=0))

    async def fake_user():
        return TelegramWebAppUser(id=4242, first_name="Override", username="ov")

    for route in app.routes:
        if getattr(route, "path", None) == "/api/me":
            dep = route.dependant.dependencies[0].call
            app.dependency_overrides[dep] = fake_user
            break

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.get("/api/me")
    assert res.status_code == 200
    assert res.json()["telegram_user_id"] == 4242


def test_dev_user_zero_not_a_user() -> None:
    s = _settings(app_env="development", webapp_dev_user_id=0)
    assert int(s.webapp_dev_user_id or 0) == 0


@pytest.mark.asyncio
async def test_user_isolation_and_api_contract(wa03_db, monkeypatch) -> None:
    from flypingavia.api.app import create_api
    import flypingavia.api.app as api_mod

    class _FakeProvider:
        async def get_trip_quote(self, *args, **kwargs):
            from flypingavia.services.prices import PriceQuote

            return PriceQuote(
                price=12_000,
                currency="RUB",
                origin_code="MOW",
                destination_code="AYT",
                transfers=0,
                airline="SU",
                source="demo",
            )

        async def get_trip_band(self, *args, **kwargs):
            from flypingavia.services.prices import PriceBand

            return PriceBand(
                cheap_max=10_000,
                typical=15_000,
                expensive_min=20_000,
                sample_size=5,
                currency="RUB",
            )

    monkeypatch.setattr(api_mod, "build_price_provider", lambda _s: _FakeProvider())
    app = create_api(_settings(app_env="test", webapp_dev_user_id=0, bot_token=TOKEN))

    now_ts = int(datetime.now(timezone.utc).timestamp())
    init_a = build_test_init_data(TOKEN, user_id=1001, auth_date=now_ts, username="a")
    init_b = build_test_init_data(TOKEN, user_id=1002, auth_date=now_ts, username="b")
    ha, hb = _auth_header(init_a), _auth_header(init_b)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        h = await c.get("/api/health")
        assert h.status_code == 200
        assert h.json()["telegram_webapp_auth"] is True
        assert "webapp_dev_user_id" not in h.json()
        assert TOKEN not in h.text

        r = await c.get("/api/ready")
        assert r.status_code in {200, 503}

        static = await c.get("/")
        assert static.status_code == 200

        assert (await c.get("/api/watches")).status_code == 401
        assert (await c.get("/api/quote", params={"origin": "MOW", "destination": "AYT"})).status_code == 401
        assert (await c.get("/api/me")).status_code == 401

        me = await c.get("/api/me", headers=ha)
        assert me.status_code == 200
        assert me.json()["telegram_user_id"] == 1001
        assert me.json()["username"] == "a"

        payload = {
            "origin": "MOW",
            "destination": "AYT",
            "max_price": 50_000,
            "depart_date": "2026-09-01",
            "flexibility_days": 3,
            "confirm_low_threshold": True,
        }
        wa = await c.post("/api/watches", headers=ha, json=payload)
        assert wa.status_code == 200, wa.text
        watch_a = wa.json()
        assert watch_a["flexibility_days"] == 3
        assert "last_checked_at" in watch_a

        wb = await c.post(
            "/api/watches",
            headers=hb,
            json={**payload, "max_price": 40_000, "origin": "LED", "destination": "IST"},
        )
        assert wb.status_code == 200, wb.text
        watch_b = wb.json()

        list_a = (await c.get("/api/watches", headers=ha)).json()
        list_b = (await c.get("/api/watches", headers=hb)).json()
        assert [w["id"] for w in list_a] == [watch_a["id"]]
        assert [w["id"] for w in list_b] == [watch_b["id"]]

        del_a = await c.delete(f"/api/watches/{watch_b['id']}", headers=ha)
        assert del_a.status_code == 404
        del_b = await c.delete(f"/api/watches/{watch_a['id']}", headers=hb)
        assert del_b.status_code == 404

        assert len((await c.get("/api/watches", headers=hb)).json()) == 1

        sneak = await c.get("/api/watches?user_id=1002", headers=ha)
        assert sneak.status_code == 200
        assert [w["id"] for w in sneak.json()] == [watch_a["id"]]

        create_sneak = await c.post(
            "/api/watches",
            headers=ha,
            json={**payload, "telegram_user_id": 1002, "max_price": 45_000},
        )
        assert create_sneak.status_code == 200
        list_b2 = (await c.get("/api/watches", headers=hb)).json()
        assert len(list_b2) == 1

        pairs = dict(parse_qsl(init_a, keep_blank_values=True))
        user_obj = json.loads(pairs["user"])
        user_obj["id"] = 1002
        pairs["user"] = json.dumps(user_obj, separators=(",", ":"), ensure_ascii=False)
        bad_init = "&".join(f"{quote(k, safe='')}={quote(v, safe='')}" for k, v in pairs.items())
        bad = await c.get("/api/watches", headers=_auth_header(bad_init))
        assert bad.status_code == 401

        ok = await c.delete(f"/api/watches/{watch_a['id']}", headers=ha)
        assert ok.status_code == 200

        low = await c.post(
            "/api/watches",
            headers=ha,
            json={
                "origin": "MOW",
                "destination": "AYT",
                "max_price": 1000,
                "depart_date": "2026-09-01",
                "confirm_low_threshold": False,
            },
        )
        assert low.status_code == 409
        assert low.json()["detail"]["code"] == "LOW_THRESHOLD_CONFIRMATION_REQUIRED"

        noauth = await c.get("/api/me")
        detail = noauth.json()["detail"]
        assert "code" in detail and "message" in detail
        assert TOKEN not in noauth.text
        assert "WebAppData" not in noauth.text


def test_frontend_wa03_contract() -> None:
    root = Path(__file__).resolve().parents[1]
    html = (root / "flypingavia/web/static/index.html").read_text(encoding="utf-8")
    js = (root / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    css = (root / "flypingavia/web/static/app.css").read_text(encoding="utf-8")

    assert 'src="/assets/telegram-web-app.js"' in html
    assert "launch-params.js" in html
    assert "diag-session.js" in html
    assert "telegram.org/js/telegram-web-app.js" not in html
    assert html.index("/assets/telegram-web-app.js") < html.index("app.js")
    assert (root / "flypingavia/web/static/telegram-web-app.js").is_file()
    assert (root / "flypingavia/web/static/launch-params.js").is_file()
    assert (root / "flypingavia/web/static/diag-session.js").is_file()

    assert "window.Telegram" in js
    assert "initData" in js
    assert "isInsideTelegramWebView" in js
    assert "waitForInitData" in js
    assert "readInitDataFromLocationHash" in js
    assert "signalTelegramReady" in js
    assert "cachedInitData" in js
    assert ".ready()" in js
    assert ".expand()" in js
    assert '"tma "' in js
    assert "localStorage.setItem" not in js
    # BUG-02.3: sessionStorage may cache recovered initData; must not invent via query injection.
    assert "__flyping__initData" in js
    assert "?initData=" not in js and "&initData=" not in js
    assert "auth-retry" in html
    assert "Повторить" in html
    assert "auth-locked" in html

    assert "showAuthGate" in js
    assert "auth-gate" in html
    assert "Загрузка FlyPing" in html
    assert "FlyPing работает внутри Telegram" in js
    assert "themeChanged" in js
    assert "enableClosingConfirmation" in js
    assert "disableClosingConfirmation" in js
    assert "bootstrapTelegramApp" in js
    assert "uiStarted" in js
    assert 'indexOf("/api/")' in js
    assert "--tg-bg-color" in css
    assert "X-Telegram-Init-Data" not in js
    assert "confirm_low_threshold" in js
    assert "flexibilityDays" in js
    assert "formatLastChecked" in js
    assert "WEBAPP_DEV_USER_ID" not in js
