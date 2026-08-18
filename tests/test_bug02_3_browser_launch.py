"""BUG-02.3 browser scenarios: URL fallback when SDK initData empty (Huawei-like)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia/web/static"

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402


def _init(uid: int = 42) -> str:
    return (
        f"query_id=AAE&user=%7B%22id%22%3A{uid}%2C%22first_name%22%3A%22A%22%7D"
        "&auth_date=1710000000&hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )


def _hash(init: str, *, spa: bool = False, double: bool = False) -> str:
    body = f"tgWebAppData={quote(init, safe='')}&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    if spa:
        body = "/route?" + body
    if double:
        body = quote(body, safe="")
    return body


@pytest.fixture
def page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Linux; Android 10; HUAWEI YAL-L21) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Version/4.0 Chrome/86.0.4240.198 Mobile Safari/537.36 Telegram-Android"
            )
        )
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()


def _serve(page, *, blank_sdk_init: bool = False):
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    sdk = (STATIC / "telegram-web-app.js").read_text(encoding="utf-8")
    lp = (STATIC / "launch-params.js").read_text(encoding="utf-8")
    diag = (STATIC / "diag-session.js").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    me_calls: list[str] = []
    diags: list[dict] = []

    def handle(route):
        url = route.request.url
        if "/assets/diag-session.js" in url:
            route.fulfill(status=200, content_type="application/javascript", body=diag)
            return
        if "/assets/launch-params.js" in url:
            route.fulfill(status=200, content_type="application/javascript", body=lp)
            return
        if "/assets/app.js" in url:
            route.fulfill(status=200, content_type="application/javascript", body=app_js)
            return
        if "/assets/telegram-web-app.js" in url:
            body = sdk
            if blank_sdk_init:
                # Force empty initData after SDK boot (simulate Huawei SDK parse failure).
                body = (
                    body
                    + "\n;try{Object.defineProperty(window.Telegram.WebApp,'initData',"
                    "{get:function(){return '';}});"
                    "window.Telegram.WebApp.initDataUnsafe={};}catch(e){}\n"
                )
            route.fulfill(status=200, content_type="application/javascript", body=body)
            return
        if "/assets/app.css" in url or "/assets/fonts.css" in url:
            route.fulfill(status=200, content_type="text/css", body=css)
            return
        if "/api/health" in url:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(
                    {
                        "ok": True,
                        "app_env": "production",
                        "telegram_bot_link": "https://t.me/FlyPingAvia_Bot",
                        "display_timezone": "Europe/Moscow",
                    }
                ),
            )
            return
        if url.endswith("/api/me"):
            auth = route.request.headers.get("authorization") or ""
            me_calls.append(auth)
            if not auth.startswith("tma ") or "hash=" not in auth:
                route.fulfill(
                    status=401,
                    content_type="application/json",
                    body=json.dumps({"detail": {"code": "INVALID_HASH", "message": "bad"}}),
                )
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"telegram_user_id": 42, "first_name": "A", "username": None}),
            )
            return
        if url.endswith("/api/diag/miniapp-bootstrap"):
            try:
                diags.append(route.request.post_data_json or {})
            except Exception:
                diags.append({})
            route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
            return
        if "app.flyping.ru" in url and "/assets/" not in url and "/api/" not in url:
            route.fulfill(status=200, content_type="text/html", body=html)
            return
        if "/assets/" in url:
            route.fulfill(status=200, body=b"")
            return
        route.fulfill(status=404, body=b"x")

    page.route("**/*", handle)
    return me_calls, diags


def _wait_ok(page, timeout=20000):
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-locked')",
        timeout=timeout,
    )


def test_normal_hash(page):
    me, _ = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash(_init(1)))
    _wait_ok(page)
    assert me and me[0].startswith("tma ")


def test_search(page):
    me, _ = _serve(page)
    page.goto("https://app.flyping.ru/?" + _hash(_init(2)))
    _wait_ok(page)
    assert me


def test_spa_hash(page):
    me, _ = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash(_init(3), spa=True))
    _wait_ok(page)
    assert me


def test_double_encoding(page):
    me, diags = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash(_init(4), double=True))
    _wait_ok(page)
    assert me
    assert any(d.get("extract_ok") or d.get("has_tgwebappdata") for d in diags)


def test_sdk_empty_url_fallback(page):
    me, diags = _serve(page, blank_sdk_init=True)
    page.goto("https://app.flyping.ru/#" + _hash(_init(5)))
    _wait_ok(page)
    assert me and "hash=" in me[0]
    assert any(d.get("stage") == "api_me_ok" for d in diags)


def test_cdn_not_required(page):
    """Local SDK + launch-params must work without telegram.org."""
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "telegram.org/js/telegram-web-app.js" not in html
    assert "/assets/telegram-web-app.js" in html
    assert "launch-params.js" in html
    me, _ = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash(_init(6)))
    _wait_ok(page)
    assert me


def test_partial_decode_reassembly(page):
    init = (
        "query_id=AAE&user=%7B%22id%22%3A11%7D&auth_date=1710000000"
        "&hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )
    me, _ = _serve(page, blank_sdk_init=True)
    page.goto(
        "https://app.flyping.ru/#tgWebAppData="
        + init
        + "&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    )
    _wait_ok(page)
    assert me


def test_hmac_still_required_invalid_rejected(page):
    """Client sends initData; server mock rejects without hash= in header path already covered.
    Here: missing hash in synthetic payload must not unlock UI via empty auth."""
    me, _ = _serve(page)
    # No launch params at all with Huawei UA + empty platform SDK
    page.add_init_script(
        """
        window.TelegramWebviewProxy = { postEvent() {} };
        """
    )
    page.goto("https://app.flyping.ru/")
    page.wait_for_timeout(2500)
    assert me == []
    title = page.inner_text("#auth-title")
    assert "сессию" not in title.lower()


def test_asset_bug023(page):
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "0.3.0-thresholdfix1" in html
    me, diags = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash(_init(9)))
    _wait_ok(page)
    assert any(d.get("asset") == "0.3.0-thresholdfix1" for d in diags)
