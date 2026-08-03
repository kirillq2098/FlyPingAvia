"""BUG-03: single /start message + WebAppInfo launch buttons + MenuButtonWebApp."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject
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


@asynccontextmanager
async def _fake_session_scope():
    yield MagicMock()


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


def test_reply_keyboard_open_is_webapp_info_not_url() -> None:
    markup = kb.main_menu("https://app.flyping.ru")
    open_btn = markup.keyboard[0][0]
    assert open_btn.text == kb.BTN_OPEN_FLYPING
    assert open_btn.web_app is not None
    assert open_btn.web_app.url == "https://app.flyping.ru/"
    assert getattr(open_btn, "url", None) in (None, "")


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


def test_handlers_start_no_longer_sends_quick_start_block() -> None:
    src = HANDLERS_PY.read_text(encoding="utf-8")
    chunk = src.split("async def cmd_start")[1].split("async def cmd_help")[0]
    assert "Быстрый старт" not in chunk


@pytest.mark.asyncio
async def test_cmd_start_sends_exactly_one_primary_message(monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.config import Settings

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        webapp_url="https://app.flyping.ru",
    )
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = next(
        o.callback for o in router.message.handlers if o.callback.__name__ == "cmd_start"
    )

    calls: list[dict] = []

    async def _answer(text, **kwargs):
        calls.append({"text": text, **kwargs})
        return MagicMock()

    message = MagicMock()
    message.from_user = MagicMock(id=91001, username="u", first_name="Тест")
    message.chat = MagicMock(id=91001)
    message.message_id = 1
    message.answer = AsyncMock(side_effect=_answer)
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )
    monkeypatch.setattr("flypingavia.bot.handlers.session_scope", _fake_session_scope)
    monkeypatch.setattr("flypingavia.bot.handlers.repo.record_user_start", AsyncMock())
    monkeypatch.setattr(
        "flypingavia.diagnostics.miniapp_session.write_diag_event",
        lambda *_a, **_k: None,
    )

    await cmd_start(message, AsyncMock(), CommandObject(command="start", args=None))

    assert len(calls) == 1
    text = calls[0]["text"]
    assert "сторож цены" in text.lower()
    assert "удобном окне" in text
    markup = calls[0]["reply_markup"]
    open_btn = markup.keyboard[0][0]
    assert open_btn.web_app is not None
    assert open_btn.web_app.url == "https://app.flyping.ru/"
    assert getattr(open_btn, "url", None) in (None, "")


@pytest.mark.asyncio
async def test_cmd_start_without_webapp_still_one_message(monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.config import Settings

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        webapp_url="",
    )
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = next(
        o.callback for o in router.message.handlers if o.callback.__name__ == "cmd_start"
    )
    calls: list[str] = []
    message = MagicMock()
    message.from_user = MagicMock(id=91002, username="u", first_name="A")
    message.chat = MagicMock(id=91002)
    message.message_id = 2
    message.answer = AsyncMock(side_effect=lambda text, **kw: calls.append(text))
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )
    monkeypatch.setattr("flypingavia.bot.handlers.session_scope", _fake_session_scope)
    monkeypatch.setattr("flypingavia.bot.handlers.repo.record_user_start", AsyncMock())
    monkeypatch.setattr(
        "flypingavia.diagnostics.miniapp_session.write_diag_event",
        lambda *_a, **_k: None,
    )

    await cmd_start(message, AsyncMock(), CommandObject(command="start", args=None))
    assert len(calls) == 1
    assert "недоступен" in calls[0].lower()
