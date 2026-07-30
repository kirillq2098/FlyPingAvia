"""Pytest defaults for FlyPingAvia."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _default_app_env(monkeypatch):
    """Тесты по умолчанию в APP_ENV=test (без production prerequisites)."""
    monkeypatch.setenv("APP_ENV", "test")
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
