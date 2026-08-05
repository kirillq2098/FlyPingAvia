"""BUG-03: single /start welcome + MenuButtonWebApp startup (unchanged by 03C)."""

from __future__ import annotations

from pathlib import Path

from aiogram.types import MenuButtonCommands, MenuButtonWebApp

from flypingavia.bot import keyboards as kb
from flypingavia.bot.menu_button import (
    MENU_BUTTON_TEXT,
    resolve_startup_menu_button,
    telegram_webapp_button_url,
)

ROOT = Path(__file__).resolve().parents[1]
MAIN_PY = ROOT / "flypingavia" / "main.py"
HANDLERS_PY = ROOT / "flypingavia" / "bot" / "handlers.py"
STATIC_APP = ROOT / "flypingavia" / "web" / "static" / "app.js"


def test_telegram_webapp_button_url_adds_trailing_slash() -> None:
    assert telegram_webapp_button_url("https://app.flyping.ru") == "https://app.flyping.ru/"
    assert telegram_webapp_button_url("https://app.flyping.ru/") == "https://app.flyping.ru/"


def test_startup_menu_button_webapp_uses_trailing_slash() -> None:
    btn = resolve_startup_menu_button("https://app.flyping.ru")
    assert isinstance(btn, MenuButtonWebApp)
    assert btn.text == MENU_BUTTON_TEXT
    assert btn.web_app.url == "https://app.flyping.ru/"


def test_startup_menu_button_stable_https_never_commands() -> None:
    btn = resolve_startup_menu_button("https://app.flyping.ru/")
    assert isinstance(btn, MenuButtonWebApp)
    assert not isinstance(btn, MenuButtonCommands)


def test_startup_menu_button_commands_only_on_tunnel() -> None:
    btn = resolve_startup_menu_button("https://abc.trycloudflare.com")
    assert isinstance(btn, MenuButtonCommands)


def test_main_verifies_menu_button_after_set() -> None:
    src = MAIN_PY.read_text(encoding="utf-8")
    assert "get_chat_menu_button" in src
    assert "set_chat_menu_button" in src
    assert "resolve_startup_menu_button" in src
    assert "MenuButtonCommands()" not in src


def test_reply_keyboard_has_no_open_webapp_button() -> None:
    markup = kb.main_menu("https://app.flyping.ru")
    texts = [btn.text for row in markup.keyboard for btn in row]
    assert kb.BTN_OPEN_FLYPING not in texts
    for row in markup.keyboard:
        for btn in row:
            assert btn.web_app is None


def test_inline_open_app_is_webapp_info_not_url() -> None:
    markup = kb.open_app_kb("https://app.flyping.ru")
    assert markup is not None
    primary = markup.inline_keyboard[0][0]
    assert primary.web_app is not None
    assert primary.web_app.url == "https://app.flyping.ru/"
    assert primary.url is None


def test_browser_fallback_copy_still_present() -> None:
    js = STATIC_APP.read_text(encoding="utf-8")
    assert "waitForInitData" in js
    assert ("обычн" in js.lower()) or ("ссылк" in js.lower()) or ("external_browser" in js)


def test_handlers_start_uses_open_app_kb_not_reply_webapp() -> None:
    src = HANDLERS_PY.read_text(encoding="utf-8")
    chunk = src.split("async def cmd_start")[1].split("async def cmd_help")[0]
    assert "Быстрый старт" not in chunk
    assert "open_app_kb" in chunk
