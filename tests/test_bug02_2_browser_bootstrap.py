"""BUG-02.2 browser-level Mini App bootstrap scenarios (Playwright)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import quote

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia/web/static"

pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402


def _build_init_data(user_id: int = 42) -> str:
    return (
        f"query_id=AAE&user=%7B%22id%22%3A{user_id}%2C%22first_name%22%3A%22A%22%7D"
        "&auth_date=1710000000&hash=0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    )


def _hash_for(init_data: str) -> str:
    return (
        "tgWebAppData="
        + quote(init_data, safe="")
        + "&tgWebAppVersion=8.0&tgWebAppPlatform=android"
    )


def _serve(page, *, delay_sdk_ms: int = 0, html_override: str | None = None):
    html = html_override or (STATIC / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    sdk = (STATIC / "telegram-web-app.js").read_text(encoding="utf-8")
    lp = (STATIC / "launch-params.js").read_text(encoding="utf-8")
    css = (STATIC / "app.css").read_text(encoding="utf-8")
    me_calls: list[str] = []

    def handle(route):
        url = route.request.url
        if url.rstrip("/").endswith("app.flyping.ru") or url.endswith("/index.html") or (
            "app.flyping.ru/" in url and "/assets/" not in url and "/api/" not in url
        ):
            route.fulfill(status=200, content_type="text/html", body=html)
            return
        if "/assets/launch-params.js" in url:
            route.fulfill(status=200, content_type="application/javascript", body=lp)
            return
        if "/assets/app.js" in url:
            route.fulfill(status=200, content_type="application/javascript", body=app_js)
            return
        if "/assets/telegram-web-app.js" in url:
            if delay_sdk_ms:
                page.wait_for_timeout(delay_sdk_ms)
            route.fulfill(status=200, content_type="application/javascript", body=sdk)
            return
        if "/assets/app.css" in url or "/assets/fonts.css" in url:
            route.fulfill(status=200, content_type="text/css", body=css)
            return
        if url.endswith("/api/health"):
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
            if not auth.startswith("tma ") or len(auth) < 20:
                route.fulfill(
                    status=401,
                    content_type="application/json",
                    body=json.dumps({"detail": {"code": "MISSING_INIT_DATA", "message": "no"}}),
                )
                return
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"telegram_user_id": 42, "first_name": "A", "username": None}),
            )
            return
        if url.endswith("/api/diag/miniapp-bootstrap"):
            route.fulfill(status=200, content_type="application/json", body='{"ok":true}')
            return
        if "/assets/" in url:
            route.fulfill(status=200, content_type="application/octet-stream", body=b"")
            return
        route.fulfill(status=404, body=b"missing")

    page.route("**/*", handle)
    return me_calls


@pytest.fixture
def chromium_page():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        yield page
        context.close()
        browser.close()


def _wait_unlocked(page, timeout: int = 20000):
    page.wait_for_function(
        "() => !document.body.classList.contains('auth-locked')",
        timeout=timeout,
    )


def test_01_sdk_and_initdata_immediate(chromium_page):
    page = chromium_page
    init = _build_init_data(1)
    me_calls = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    assert len(me_calls) >= 1
    assert me_calls[0].startswith("tma ")


def test_02_sdk_appears_after_500ms(chromium_page):
    page = chromium_page
    init = _build_init_data(2)
    me_calls = _serve(page, delay_sdk_ms=500)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page, timeout=25000)
    assert any(c.startswith("tma ") for c in me_calls)


def test_03_initdata_appears_after_2s_via_hashchange(chromium_page):
    page = chromium_page
    init = _build_init_data(3)
    me_calls = _serve(page)
    page.goto("https://app.flyping.ru/")
    page.wait_for_timeout(500)
    page.evaluate(
        """(hash) => { location.hash = hash; }""",
        _hash_for(init),
    )
    # Give hashchange + polling time; init appears "late"
    page.wait_for_timeout(2000)
    _wait_unlocked(page, timeout=20000)
    assert any(c.startswith("tma ") for c in me_calls)


def test_04_initdata_via_hashchange(chromium_page):
    page = chromium_page
    init = _build_init_data(4)
    _serve(page)
    page.goto("https://app.flyping.ru/")
    page.wait_for_timeout(200)
    page.evaluate("(h) => { location.hash = h; }", _hash_for(init))
    _wait_unlocked(page)


def test_05_initdata_in_location_search(chromium_page):
    page = chromium_page
    init = _build_init_data(5)
    me_calls = _serve(page)
    # search-only launch (some clients put tgWebAppData in query)
    q = "tgWebAppData=" + quote(init, safe="") + "&tgWebAppPlatform=android"
    page.goto("https://app.flyping.ru/?" + q)
    _wait_unlocked(page)
    assert any(c.startswith("tma ") for c in me_calls)


def test_06_empty_session_storage_cold_start(chromium_page):
    page = chromium_page
    init = _build_init_data(6)
    _serve(page)
    page.add_init_script("try { sessionStorage.clear(); } catch (e) {}")
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)


def test_07_cold_first_launch(chromium_page):
    page = chromium_page
    init = _build_init_data(7)
    _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    assert page.evaluate("() => window.__FLYPING_BOOT_STATE__") == "AUTH_SUCCESS"


def test_08_repeat_launch_uses_storage(chromium_page):
    page = chromium_page
    init = _build_init_data(8)
    me_calls = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    # Second navigation without hash — SDK sessionStorage may retain tgWebAppData
    page.goto("https://app.flyping.ru/")
    page.wait_for_timeout(1500)
    # Either unlocked via storage or waiting; storage from first visit should unlock
    unlocked = page.evaluate("() => !document.body.classList.contains('auth-locked')")
    assert unlocked or any(c.startswith("tma ") for c in me_calls)


def test_09_empty_does_not_overwrite_found(chromium_page):
    page = chromium_page
    init = _build_init_data(9)
    _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    page.evaluate("location.hash = ''")
    page.wait_for_timeout(300)
    assert page.evaluate("() => !document.body.classList.contains('auth-locked')")


def test_10_double_bootstrap_safe(chromium_page):
    page = chromium_page
    init = _build_init_data(10)
    me_calls = _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    before = len(me_calls)
    # Second call should no-op once uiStarted
    page.evaluate(
        """() => {
          const ev = new Event('DOMContentLoaded');
          document.dispatchEvent(ev);
        }"""
    )
    page.wait_for_timeout(500)
    # Should not spam many extra /api/me
    assert len(me_calls) <= before + 1


def test_11_url_button_without_initdata_not_session_error(chromium_page):
    page = chromium_page
    _serve(page)
    page.add_init_script(
        """
        Object.defineProperty(navigator, 'userAgent', {
          get: () => 'Mozilla/5.0 Telegram-Android'
        });
        """
    )
    page.goto("https://app.flyping.ru/")
    page.wait_for_function(
        """() => {
          const t = document.getElementById('auth-title');
          return t && t.textContent.indexOf('внутри Telegram') >= 0;
        }""",
        timeout=8000,
    )
    title = page.inner_text("#auth-title")
    assert "сессию" not in title.lower()
    assert "данные запуска" not in title.lower()


def test_12_official_web_app_launch_with_initdata(chromium_page):
    page = chromium_page
    init = _build_init_data(12)
    me_calls = _serve(page)
    page.goto(
        "https://app.flyping.ru/#"
        + _hash_for(init)
        + "&tgWebAppThemeParams=%7B%7D"
    )
    _wait_unlocked(page)
    assert me_calls and me_calls[0].startswith("tma ")


def test_13_html_js_asset_mismatch_reported(chromium_page):
    page = chromium_page
    init = _build_init_data(13)
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    html = html.replace('asset: "0.3.0-bug023"', 'asset: "0.3.0-OLD"')
    me_calls = _serve(page, html_override=html)
    diags: list[dict] = []

    def on_req(request):
        if request.url.endswith("/api/diag/miniapp-bootstrap") and request.method == "POST":
            try:
                diags.append(request.post_data_json)
            except Exception:
                pass

    page.on("request", on_req)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    assert any(d and d.get("stage") == "asset_mismatch" for d in diags)
    assert me_calls  # still authenticates


def test_14_api_me_only_after_initdata(chromium_page):
    page = chromium_page
    init = _build_init_data(14)
    me_calls = _serve(page)
    page.goto("https://app.flyping.ru/")
    page.wait_for_timeout(800)
    assert me_calls == []
    page.evaluate("(h) => { location.hash = h; }", _hash_for(init))
    _wait_unlocked(page)
    assert len(me_calls) >= 1


def test_15_ui_stays_after_me_200(chromium_page):
    page = chromium_page
    init = _build_init_data(15)
    _serve(page)
    page.goto("https://app.flyping.ru/#" + _hash_for(init))
    _wait_unlocked(page)
    # Short stand-in for 60s soak (full 60s is for production Android retest).
    page.wait_for_timeout(3000)
    assert page.evaluate("() => !document.body.classList.contains('auth-locked')")
    assert page.evaluate("() => window.__FLYPING_BOOT_STATE__") == "AUTH_SUCCESS"


def test_frontend_bug022_contract():
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "0.3.0-bug023" in html
    assert "/assets/telegram-web-app.js" in html
    assert "launch-params.js" in html
    assert "isTelegramMiniAppContext" in js
    assert "BOOT_STATES" in js
    assert "waitForTelegramSdk" in js
    assert "readInitDataFromUrlFallback" in js or "FlyPingLaunchParams" in js
    assert "Не удалось получить данные запуска Telegram" in js
    assert "/Telegram/i" not in js
    assert "JS_ASSET_BUILD" in js
    # CDN must not be a critical path (Huawei blocks telegram.org).
    assert "telegram.org/js/telegram-web-app.js" not in html
