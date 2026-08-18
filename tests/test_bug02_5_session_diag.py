"""BUG-02.5: safe Mini App session diagnostics."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from flypingavia.diagnostics.miniapp_session import (
    classify_session_events,
    sanitize_record,
    sanitize_ua,
    write_diag_event,
)


def test_sanitize_strips_secrets():
    clean = sanitize_record(
        {
            "event": "bootstrap_start",
            "session_id": "abc",
            "authorization": "tma SECRET",
            "init_data": "user=1&hash=abc",
            "ua": "Mozilla Telegram-Android",
            "has_tgwebappdata": False,
        }
    )
    assert "authorization" not in clean
    assert "init_data" not in clean
    assert clean["event"] == "bootstrap_start"
    assert "SECRET" not in sanitize_ua("Authorization: Bearer SUPERSECRETTOKEN")


def test_classify_absent_tgdata():
    assert (
        classify_session_events(
            [{"event": "missing_init_data", "has_tgwebappdata": False, "init_data_len": 0}]
        )
        == "A"
    )


def test_classify_parser_fail():
    assert (
        classify_session_events(
            [
                {
                    "event": "launch_parser_result",
                    "has_tgwebappdata": True,
                    "tgwebappdata_len": 400,
                    "extract_ok": False,
                    "has_init_data": False,
                }
            ]
        )
        == "B"
    )


def test_write_diag_event_jsonl(tmp_path, monkeypatch):
    log = tmp_path / "miniapp-diagnostic.log"
    monkeypatch.setenv("MINIAPP_DIAG_LOG_PATH", str(log))
    assert write_diag_event(
        {
            "kind": "frontend",
            "event": "html_loaded",
            "session_id": "sess-1",
            "asset": "0.3.0-thresholdfix1",
        }
    )
    text = log.read_text(encoding="utf-8")
    assert "sess-1" in text
    assert "html_loaded" in text
    assert "bot_token" not in text


@pytest.mark.asyncio
async def test_diag_endpoint_writes_session(tmp_path, monkeypatch):
    log = tmp_path / "miniapp-diagnostic.log"
    monkeypatch.setenv("MINIAPP_DIAG_LOG_PATH", str(log))
    monkeypatch.setenv("BOT_TOKEN", "diag-test-bot-token-not-real")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("WEBAPP_URL", "https://app.flyping.ru")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TRAVELPAYOUTS_TOKEN", "tok")
    from flypingavia.config import get_settings
    import flypingavia.db.session as sess

    get_settings.cache_clear()
    sess._engine = None
    sess._session_factory = None
    from flypingavia.api.app import create_api
    from flypingavia.config import Settings

    app = create_api(
        Settings(
            bot_token="diag-test-bot-token-not-real",
            app_env="production",
            webapp_url="https://app.flyping.ru",
            travelpayouts_token="tok",
            webapp_dev_user_id=0,
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.post(
            "/api/diag/miniapp-bootstrap",
            json={
                "session_id": "unit-sess",
                "event": "bootstrap_start",
                "asset": "0.3.0-thresholdfix1",
                "launch_mode": "telegram_browser",
                "has_tgwebappdata": False,
                "platform": "android",
            },
            headers={"X-Diag-Session": "unit-sess"},
        )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    body = log.read_text(encoding="utf-8")
    assert "unit-sess" in body
    assert "bootstrap_start" in body
    assert "diag-test-bot-token" not in body


def test_frontend_bug025_contract():
    root = Path(__file__).resolve().parents[1]
    html = (root / "flypingavia/web/static/index.html").read_text(encoding="utf-8")
    js = (root / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    diag = (root / "flypingavia/web/static/diag-session.js").read_text(encoding="utf-8")
    assert "0.3.0-thresholdfix1" in html
    assert "diag-session.js" in html
    assert "FlyPingDiag" in diag
    assert "X-Diag-Session" in js
    assert "telegram_browser" in diag
    assert "обычную ссылку" in js
    assert "collect-miniapp-session.sh" in (
        root / "scripts/collect-miniapp-session.sh"
    ).read_text(encoding="utf-8")
    # HMAC / parser files still present; auth path unchanged marker
    assert '"tma "' in js
    assert "validate_telegram_init_data" in (
        root / "flypingavia/api/telegram_auth.py"
    ).read_text(encoding="utf-8")
