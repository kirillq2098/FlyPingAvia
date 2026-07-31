"""IN-04: production Mini App hosting, WebApp menu button, /start keyboard."""

from __future__ import annotations

import re
from pathlib import Path

from aiogram.types import MenuButtonCommands, MenuButtonWebApp

from flypingavia.bot import keyboards as kb
from flypingavia.bot.menu_button import MENU_BUTTON_TEXT, resolve_startup_menu_button
from flypingavia.version import FALLBACK_VERSION, __version__

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "flypingavia" / "web" / "static"
LANDING = ROOT / "deploy" / "landing" / "index.html"
MAIN_PY = ROOT / "flypingavia" / "main.py"


def test_version_unchanged_030() -> None:
    assert __version__ == "0.3.0"
    assert FALLBACK_VERSION == "0.3.0"
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'version = "0.3.0"' in pyproject


def test_startup_menu_button_webapp_production_url() -> None:
    btn = resolve_startup_menu_button("https://app.flyping.ru")
    assert isinstance(btn, MenuButtonWebApp)
    assert btn.text == MENU_BUTTON_TEXT == "FlyPing"
    assert btn.web_app.url == "https://app.flyping.ru"


def test_startup_menu_button_commands_on_tunnel() -> None:
    btn = resolve_startup_menu_button("https://abc.trycloudflare.com")
    assert isinstance(btn, MenuButtonCommands)


def test_startup_menu_button_skipped_without_url() -> None:
    assert resolve_startup_menu_button(None) is None
    assert resolve_startup_menu_button("") is None


def test_main_uses_ensure_webapp_menu_button() -> None:
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "resolve_startup_menu_button" in src
    assert "set_chat_menu_button" in src
    assert "MenuButtonCommands()" not in src
    assert "ensure-menu-button" in src


def test_start_reply_keyboard_uses_webapp_info_not_tme_url() -> None:
    markup = kb.main_menu("https://app.flyping.ru")
    open_btn = markup.keyboard[0][0]
    assert open_btn.text == kb.BTN_OPEN_FLYPING
    assert open_btn.web_app is not None
    assert open_btn.web_app.url == "https://app.flyping.ru"
    assert getattr(open_btn, "url", None) in (None, "")


def test_open_app_inline_primary_is_webapp() -> None:
    markup = kb.open_app_kb("https://app.flyping.ru")
    assert markup is not None
    primary = markup.inline_keyboard[0][0]
    assert primary.web_app is not None
    assert primary.web_app.url == "https://app.flyping.ru"
    assert primary.url is None
    # Optional browser row is plain URL to Mini App host — not t.me bot loop.
    browser = markup.inline_keyboard[1][0]
    assert browser.url == "https://app.flyping.ru"
    assert "t.me/" not in (browser.url or "")


def test_mini_app_index_uses_local_telegram_sdk() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'src="/assets/telegram-web-app.js"' in html
    assert html.index("/assets/telegram-web-app.js") < html.index("app.js")
    assert (STATIC / "telegram-web-app.js").is_file()


def test_mini_app_separates_browser_fallback_from_telegram_mode() -> None:
    js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "isInsideTelegramWebView" in js
    assert "waitForInitData" in js
    assert "allowBotLink" in js
    # Bot deep-link must not be shown inside Telegram WebView.
    assert "isInsideTelegramWebView()" in js
    assert 'gateBotLink = isInsideTelegramWebView() ? "" : botLink' in js or (
        'insideTelegram ? "" : botLink' in js
    )


def test_mini_app_index_cache_bust_and_no_redirect_to_bot() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "t.me/" not in html
    assert "location.href" not in html or "t.me" not in html
    assert "meta http-equiv=\"refresh\"" not in html.lower()
    assert "app.js?v=0.3.0" in html
    assert "app.css?v=0.3.0" in html


def test_index_route_sends_no_cache_headers() -> None:
    src = (ROOT / "flypingavia" / "api" / "app.py").read_text(encoding="utf-8")
    assert "Cache-Control" in src
    assert "no-store" in src


def test_landing_is_stub_not_mini_app_and_uses_production_bot() -> None:
    """Public flyping.ru currently serves deploy/landing stub — not Mini App."""
    landing = LANDING.read_text(encoding="utf-8")
    mini = (STATIC / "index.html").read_text(encoding="utf-8")
    assert "auth-gate" not in landing
    assert "telegram-web-app.js" not in landing
    assert "FlyPingAvia_Bot" in landing
    assert "t.me/FlyPingBot" not in landing
    # Distinct entrypoints
    assert "auth-gate" in mini
    assert "panel-search" in mini


def test_frontend_dirs_inventory() -> None:
    """Marketing Next.js lives in website/; Mini App + stub remain as HTML entrypoints."""
    html_files = sorted(
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("index.html")
        if ".git" not in p.parts
        and "__pycache__" not in p.parts
        and "node_modules" not in p.parts
        and ".next" not in p.parts
    )
    assert "deploy/landing/index.html" in html_files
    assert "flypingavia/web/static/index.html" in html_files
    assert (ROOT / "website" / "app" / "page.tsx").is_file()
    assert (ROOT / "website" / "package.json").is_file()


def test_no_secrets_in_tracked_files() -> None:
    # Match realistic leaked tokens, not documentation substrings.
    forbidden = re.compile(
        r"(?i)("
        r"bot_token\s*=\s*['\"][0-9]{6,}:[A-Za-z0-9_-]{30,}"
        r"|sk_live_[A-Za-z0-9]{16,}"
        r"|-----BEGIN (RSA |OPENSSH )?PRIVATE KEY-----"
        r")"
    )
    checked = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(
            part in {".git", "__pycache__", ".pytest_cache", "data", "node_modules"}
            for part in path.parts
        ):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"}:
            continue
        if path.name in {".env"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        assert not forbidden.search(text), f"secret-like pattern in {path}"
        checked += 1
    assert checked > 50


def test_gitignore_covers_env() -> None:
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in gi
