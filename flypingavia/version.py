"""Единый источник runtime-версии FlyPingAvia (RL-02).

Источник истины для установленного пакета — distribution metadata
из `pyproject.toml` (`name = "flypingavia"`). При запуске из checkout
без metadata используется FALLBACK_VERSION (должен совпадать с pyproject).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

PACKAGE_NAME = "flypingavia"
FALLBACK_VERSION = "0.3.0"


def get_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return FALLBACK_VERSION


__version__ = get_version()
