"""WA-02: APP_ENV, WEBAPP_URL, health/ready, Telegram button."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from flypingavia.bot import keyboards as kb
from flypingavia.bot.formatters import mini_app_unavailable_text
from flypingavia.config import Settings
from flypingavia.webapp_url import (
    is_telegram_safe_webapp_url,
    is_temporary_tunnel_hostname,
    normalize_webapp_url,
)


def _settings(**kwargs) -> Settings:
    base = {
        "bot_token": "1:TEST",
        "app_env": "development",
        "webapp_dev_user_id": 0,
        "travelpayouts_token": "",
    }
    base.update(kwargs)
    return Settings(**base)


# --- Settings / URL ---


def test_dev_empty_url_ok() -> None:
    s = _settings(app_env="development", webapp_url="")
    assert s.webapp_url == ""
    assert s.telegram_webapp_url is None
    assert s.is_ready is True


def test_production_empty_url_error() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(app_env="production", webapp_url="")


def test_production_public_http_error() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(app_env="production", webapp_url="http://app.example.com")


def test_production_https_ok() -> None:
    s = _settings(
        app_env="production",
        webapp_url="https://app.example.com",
        travelpayouts_token="tok",
    )
    assert s.webapp_url == "https://app.example.com"
    assert s.webapp_https is True
    assert s.telegram_webapp_url == "https://app.example.com"
    assert s.is_ready is True


def test_localhost_http_dev_ok() -> None:
    s = _settings(app_env="development", webapp_url="http://127.0.0.1:8080")
    assert s.webapp_url == "http://127.0.0.1:8080"
    assert s.telegram_webapp_url is None  # не для Telegram users


def test_localhost_http_production_error() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(app_env="production", webapp_url="http://localhost:8080")


def test_url_query_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_webapp_url("https://app.example.com?x=1", app_env="development")


def test_url_fragment_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_webapp_url("https://app.example.com#x", app_env="development")


def test_url_userinfo_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_webapp_url("https://user:pass@app.example.com", app_env="development")


def test_url_path_rejected() -> None:
    with pytest.raises(ValueError):
        normalize_webapp_url("https://app.example.com/index.html", app_env="development")


def test_trailing_slash_normalized() -> None:
    assert (
        normalize_webapp_url("https://App.Example.COM/", app_env="development")
        == "https://app.example.com"
    )


def test_invalid_app_env() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(app_env="staging")


def test_production_dev_user_rejected() -> None:
    with pytest.raises((ValidationError, ValueError)):
        _settings(
            app_env="production",
            webapp_url="https://app.example.com",
            webapp_dev_user_id=1,
            travelpayouts_token="tok",
        )


def test_default_https_port_stripped() -> None:
    assert (
        normalize_webapp_url("https://app.example.com:443", app_env="development")
        == "https://app.example.com"
    )


def test_production_rejects_trycloudflare_subdomain() -> None:
    with pytest.raises((ValidationError, ValueError), match="trycloudflare"):
        _settings(
            app_env="production",
            webapp_url="https://abc.trycloudflare.com",
            travelpayouts_token="tok",
        )


def test_production_rejects_trycloudflare_apex() -> None:
    with pytest.raises((ValidationError, ValueError), match="trycloudflare"):
        _settings(
            app_env="production",
            webapp_url="https://trycloudflare.com",
            travelpayouts_token="tok",
        )


def test_development_allows_trycloudflare() -> None:
    s = _settings(
        app_env="development",
        webapp_url="https://abc.trycloudflare.com",
    )
    assert s.webapp_url == "https://abc.trycloudflare.com"
    assert s.telegram_webapp_url == "https://abc.trycloudflare.com"


def test_test_env_allows_trycloudflare() -> None:
    s = _settings(
        app_env="test",
        webapp_url="https://xyz.trycloudflare.com",
    )
    assert s.webapp_url == "https://xyz.trycloudflare.com"


def test_production_allows_custom_https_domain() -> None:
    s = _settings(
        app_env="production",
        webapp_url="https://app.example.com",
        travelpayouts_token="tok",
    )
    assert s.webapp_url == "https://app.example.com"
    assert s.is_ready is True


def test_production_allows_named_tunnel_custom_hostname() -> None:
    s = _settings(
        app_env="production",
        webapp_url="https://mini.flyping.ru",
        travelpayouts_token="tok",
    )
    assert s.webapp_url == "https://mini.flyping.ru"
    assert is_temporary_tunnel_hostname("mini.flyping.ru") is False


def test_trycloudflare_suffix_not_false_positive() -> None:
    assert is_temporary_tunnel_hostname("trycloudflare.com.example.org") is False
    assert is_temporary_tunnel_hostname("eviltrycloudflare.com") is False
    s = _settings(
        app_env="production",
        webapp_url="https://trycloudflare.com.example.org",
        travelpayouts_token="tok",
    )
    assert s.webapp_url == "https://trycloudflare.com.example.org"


def test_temporary_hostname_case_insensitive() -> None:
    assert is_temporary_tunnel_hostname("ABC.TryCloudflare.COM") is True
    with pytest.raises((ValidationError, ValueError), match="trycloudflare"):
        normalize_webapp_url(
            "https://ABC.TryCloudflare.COM",
            app_env="production",
        )


# --- health / ready ---


@pytest.mark.asyncio
async def test_health_development(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "wa.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    monkeypatch.setenv("WEBAPP_URL", "")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from flypingavia.db.session import init_db
    import flypingavia.db.session as db_session
    from httpx import ASGITransport, AsyncClient

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None
    await init_db()
    app = create_api(get_settings())
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        res = await c.get("/api/health")
        body = res.json()
        assert res.status_code == 200
        assert body["status"] == "ok"
        assert body["app_env"] == "development"
        assert body["ready"] is True
        assert body["display_timezone"] == "Europe/Moscow"
        assert "bot_token" not in body
        assert "TRAVELPAYOUTS" not in str(body)
        assert "database" not in str(body).lower()

        ready = await c.get("/api/ready")
        assert ready.status_code == 200
        assert ready.json()["ready"] is True

    await db_session._engine.dispose()
    db_session._engine = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_health_production_ready_and_demo(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "wa2.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("WEBAPP_URL", "https://app.example.com/")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "live-token")
    from flypingavia.config import get_settings
    from flypingavia.api.app import create_api
    from flypingavia.db.session import init_db
    import flypingavia.db.session as db_session
    from httpx import ASGITransport, AsyncClient

    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None
    await init_db()
    s = get_settings()
    assert s.webapp_url == "https://app.example.com"
    app = create_api(s)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        ok = await c.get("/api/health")
        assert ok.json()["ready"] is True
        assert ok.json()["webapp_https"] is True
        assert (await c.get("/api/ready")).status_code == 200

    # demo prices → not ready
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "")
    get_settings.cache_clear()
    s2 = get_settings()
    assert "DEMO_PRICES_ENABLED" in s2.readiness_issues()
    app2 = create_api(s2)
    async with AsyncClient(transport=ASGITransport(app=app2), base_url="http://test") as c:
        h = await c.get("/api/health")
        assert h.status_code == 200
        assert h.json()["ready"] is False
        assert "DEMO_PRICES_ENABLED" in h.json()["issues"]
        r = await c.get("/api/ready")
        assert r.status_code == 503
        assert r.json()["ready"] is False

    await db_session._engine.dispose()
    db_session._engine = None
    get_settings.cache_clear()


# --- Telegram button ---


def test_https_creates_webapp_button() -> None:
    markup = kb.main_menu("https://app.example.com")
    texts = [btn.text for row in markup.keyboard for btn in row]
    assert "🛩 Открыть приложение" in texts
    web = markup.keyboard[0][0]
    assert web.web_app is not None
    assert web.web_app.url == "https://app.example.com"


def test_empty_url_no_broken_button() -> None:
    markup = kb.main_menu(None)
    texts = [btn.text for row in markup.keyboard for btn in row]
    assert "🛩 Открыть приложение" not in texts
    assert "➕ Добавить" in texts
    assert kb.open_app_kb(None) is None


def test_localhost_not_telegram_safe() -> None:
    assert is_telegram_safe_webapp_url("http://127.0.0.1:8080") is False
    assert is_telegram_safe_webapp_url("https://localhost") is False
    s = _settings(webapp_url="http://127.0.0.1:8080")
    assert s.telegram_webapp_url is None
    assert kb.open_app_kb(s.telegram_webapp_url) is None


def test_canonical_url_no_extra_path() -> None:
    markup = kb.open_app_kb("https://app.example.com")
    assert markup is not None
    assert markup.inline_keyboard[0][0].web_app.url == "https://app.example.com"
    assert "/index" not in markup.inline_keyboard[0][0].web_app.url


def test_unavailable_message() -> None:
    text = mini_app_unavailable_text()
    assert "недоступен" in text.lower()
    assert "команд" in text.lower()


# --- frontend / deploy artifacts ---


def test_frontend_same_origin_api() -> None:
    src = (Path(__file__).resolve().parents[1] / "flypingavia/web/static/app.js").read_text(
        encoding="utf-8"
    )
    assert 'api("/api/watches")' in src or 'apiFetch("/api/watches")' in src
    assert "http://127.0.0.1" not in src or "formatLastChecked" in src
    # relative API paths (WA-03: apiFetch / api alias)
    assert '"/api/watches"' in src
    assert "trycloudflare" not in src


def test_deploy_examples_exist() -> None:
    root = Path(__file__).resolve().parents[1]
    assert (root / "deploy/nginx/flyping.conf.example").is_file()
    assert (root / "deploy/caddy/Caddyfile.example").is_file()
    assert (root / "deploy/cloudflared/config.yml.example").is_file()
    assert (root / "deploy/docker-compose.production.example.yml").is_file()
    assert (root / "docs/PRODUCTION_CHECKLIST.md").is_file()
    cf = (root / "deploy/cloudflared/config.yml.example").read_text(encoding="utf-8")
    assert "trycloudflare" in cf.lower() or "temporary" in cf.lower() or "development" in cf.lower()
    assert "<TUNNEL_ID>" in cf


def test_dockerfile_non_root_and_no_env_secrets() -> None:
    text = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text(encoding="utf-8")
    assert "USER appuser" in text
    assert "HEALTHCHECK" in text
    assert "COPY .env" not in text
    assert "BOT_TOKEN=" not in text
