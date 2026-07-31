"""Pytest defaults for FlyPingAvia."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_app_env(monkeypatch):
    """Тесты по умолчанию в APP_ENV=test (без production prerequisites)."""
    monkeypatch.setenv("APP_ENV", "test")
    # Стабильный secret для production Settings() в WA-02/WA-03 и т.п.
    monkeypatch.setenv(
        "WATCH_SHARE_CALLBACK_SECRET",
        "test-watch-share-callback-secret-32chars!!",
    )
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
