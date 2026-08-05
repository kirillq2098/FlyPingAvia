"""BUG-03C: Reply Keyboard without WebApp; /start uses inline open_app_kb."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject

from flypingavia.bot import keyboards as kb
from flypingavia.bot.menu_button import telegram_webapp_button_url

ROOT = Path(__file__).resolve().parents[1]
HANDLERS_PY = ROOT / "flypingavia" / "bot" / "handlers.py"
STATIC_APP = ROOT / "flypingavia" / "web" / "static" / "app.js"


@asynccontextmanager
async def _fake_session_scope():
    yield MagicMock()


def test_telegram_webapp_button_url_trailing_slash() -> None:
    assert telegram_webapp_button_url("https://app.flyping.ru") == "https://app.flyping.ru/"
    assert telegram_webapp_button_url("https://app.flyping.ru/") == "https://app.flyping.ru/"


def test_main_menu_has_no_keyboard_button_web_app() -> None:
    markup = kb.main_menu("https://app.flyping.ru")
    texts = [btn.text for row in markup.keyboard for btn in row]
    assert kb.BTN_OPEN_FLYPING not in texts
    for row in markup.keyboard:
        for btn in row:
            assert getattr(btn, "web_app", None) in (None, )
            assert btn.web_app is None


def test_main_menu_keeps_action_buttons() -> None:
    markup = kb.main_menu("https://app.flyping.ru")
    texts = [btn.text for row in markup.keyboard for btn in row]
    assert kb.BTN_CREATE_WATCH in texts
    assert kb.BTN_MY_WATCHES in texts
    assert kb.BTN_CHECK_PRICES in texts
    assert kb.BTN_HELP in texts
    assert len(markup.keyboard) == 2


def test_open_app_kb_is_inline_webapp_with_trailing_slash() -> None:
    markup = kb.open_app_kb("https://app.flyping.ru")
    assert markup is not None
    primary = markup.inline_keyboard[0][0]
    assert primary.text == kb.BTN_OPEN_FLYPING
    assert primary.web_app is not None
    assert primary.web_app.url == "https://app.flyping.ru/"
    assert primary.url is None


def test_handlers_start_uses_open_app_kb() -> None:
    src = HANDLERS_PY.read_text(encoding="utf-8")
    chunk = src.split("async def cmd_start")[1].split("async def cmd_help")[0]
    assert "open_app_kb" in chunk
    assert "inline_keyboard_web_app" in chunk
    assert "reply_keyboard_web_app" not in chunk


def test_browser_fallback_remains_safe_without_false_session() -> None:
    js = STATIC_APP.read_text(encoding="utf-8")
    assert "waitForInitData" in js
    assert "missing_init_data" in js
    assert "showAuthGate" in js
    # Must not invent auth without initData
    assert "/api/me" in js
    assert "getInitData()" in js


@pytest.mark.asyncio
async def test_cmd_start_one_welcome_with_inline_webapp(monkeypatch) -> None:
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

    # One welcome/CTA message + one reply-keyboard sync (no second Open button).
    assert len(calls) == 2
    welcome = calls[0]
    assert "сторож цены" in welcome["text"].lower()
    assert "удобном окне" in welcome["text"]
    markup = welcome["reply_markup"]
    primary = markup.inline_keyboard[0][0]
    assert primary.web_app is not None
    assert primary.web_app.url == "https://app.flyping.ru/"
    assert getattr(primary, "url", None) in (None, "")
    assert primary.text == kb.BTN_OPEN_FLYPING

    sync = calls[1]
    assert sync["text"] == "Главное меню:"
    reply_texts = [btn.text for row in sync["reply_markup"].keyboard for btn in row]
    assert kb.BTN_OPEN_FLYPING not in reply_texts
    assert kb.BTN_CREATE_WATCH in reply_texts
    for row in sync["reply_markup"].keyboard:
        for btn in row:
            assert btn.web_app is None

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
