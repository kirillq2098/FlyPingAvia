from __future__ import annotations

import asyncio
import logging

import pytest
from pydantic import ValidationError

from flypingavia.config import Settings
from flypingavia.main import _build_bot, _log_startup_summary


def _settings(**kwargs) -> Settings:
    values = {
        "app_env": "test",
        "bot_token": "123456:TEST_TOKEN",
        "telegram_api_gateway_url": "",
        "telegram_api_gateway_secret": "",
    }
    values.update(kwargs)
    return Settings(_env_file=None, **values)


def test_gateway_default_is_direct() -> None:
    settings = _settings()
    assert settings.telegram_api_gateway_enabled is False
    bot = _build_bot(settings)
    try:
        assert bot.session.api.base == "https://api.telegram.org/bot{token}/{method}"
        assert bot.session.api.file == "https://api.telegram.org/file/bot{token}/{path}"
    finally:
        asyncio.run(bot.session.close())


def test_gateway_url_is_normalized_and_templates_are_correct() -> None:
    settings = _settings(
        telegram_api_gateway_url="  https://gateway.example.workers.dev///  ",
        telegram_api_gateway_secret="super-secret-path",
    )
    assert settings.telegram_api_gateway_url == "https://gateway.example.workers.dev"
    assert settings.telegram_api_gateway_enabled is True

    bot = _build_bot(settings)
    try:
        assert bot.session.api.base == (
            "https://gateway.example.workers.dev/super-secret-path/api/{method}"
        )
        assert bot.session.api.file == (
            "https://gateway.example.workers.dev/super-secret-path/file/{path}"
        )
    finally:
        asyncio.run(bot.session.close())


def test_gateway_requires_secret() -> None:
    with pytest.raises(ValidationError, match="TELEGRAM_API_GATEWAY_SECRET"):
        _settings(
            telegram_api_gateway_url="https://gateway.example.workers.dev",
            telegram_api_gateway_secret="",
        )


def test_gateway_requires_https() -> None:
    with pytest.raises(ValidationError, match="HTTPS"):
        _settings(
            telegram_api_gateway_url="http://gateway.example.test",
            telegram_api_gateway_secret="secret",
        )


def test_gateway_secret_is_not_logged(caplog: pytest.LogCaptureFixture) -> None:
    secret = "must-never-appear-in-logs"
    settings = _settings(
        telegram_api_gateway_url="https://gateway.example.workers.dev",
        telegram_api_gateway_secret=secret,
    )

    with caplog.at_level(logging.INFO, logger="flypingavia"):
        _log_startup_summary(settings)

    text = caplog.text
    assert "Telegram API transport: gateway" in text
    assert secret not in text
    assert settings.bot_token not in text
