"""WA-02: валидация и нормализация публичного WEBAPP_URL."""

from __future__ import annotations

from urllib.parse import urlparse, urlunparse

ALLOWED_APP_ENVS = frozenset({"development", "production", "test"})

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _is_local_hostname(hostname: str | None) -> bool:
    if not hostname:
        return False
    host = hostname.lower().rstrip(".")
    return host in _LOCAL_HOSTS


def normalize_webapp_url(raw: str, *, app_env: str) -> str:
    """Проверить и нормализовать WEBAPP_URL.

    Пустая строка допустима вне production.
    Canonical: схема+host[+non-default port], без path/query/fragment/userinfo,
    без завершающего ``/``, hostname в нижнем регистре.
    """
    value = (raw or "").strip()
    if not value:
        if app_env == "production":
            raise ValueError(
                "В production обязателен WEBAPP_URL=https://… "
                "(постоянный HTTPS без временного tunnel)"
            )
        return ""

    if any(ch.isspace() for ch in value):
        raise ValueError("WEBAPP_URL не должен содержать пробелы")

    parsed = urlparse(value)
    if not parsed.scheme:
        raise ValueError(
            "WEBAPP_URL должен включать схему (https://… или http://localhost…)"
        )
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"WEBAPP_URL: неподдерживаемая схема {parsed.scheme!r}")

    if parsed.username is not None or parsed.password is not None:
        raise ValueError("WEBAPP_URL не должен содержать userinfo")
    if parsed.query:
        raise ValueError("WEBAPP_URL не должен содержать query string")
    if parsed.fragment:
        raise ValueError("WEBAPP_URL не должен содержать fragment")

    path = parsed.path or ""
    if path not in {"", "/"}:
        raise ValueError(
            "WEBAPP_URL для MVP должен быть корнем домена "
            "(без path вроде /index.html). Пример: https://app.example.com"
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("WEBAPP_URL: отсутствует hostname")

    is_local = _is_local_hostname(hostname)
    if scheme == "http":
        if not is_local:
            raise ValueError(
                "Публичный HTTP запрещён. Используйте HTTPS или http://localhost "
                "только для локальной разработки"
            )
        if app_env == "production":
            raise ValueError(
                "В production запрещён localhost HTTP. Укажите HTTPS WEBAPP_URL"
            )
    elif scheme == "https":
        pass
    else:
        raise ValueError(f"WEBAPP_URL: неподдерживаемая схема {scheme!r}")

    # Не сохраняем default ports как часть origin.
    port = parsed.port
    if scheme == "https" and port == 443:
        port = None
    if scheme == "http" and port == 80:
        port = None

    netloc = hostname
    if port is not None:
        netloc = f"{hostname}:{port}"

    return urlunparse((scheme, netloc, "", "", "", ""))


def is_telegram_safe_webapp_url(url: str) -> bool:
    """URL, который можно отдавать пользователям Telegram как Web App кнопку."""
    if not url:
        return False
    parsed = urlparse(url)
    if parsed.scheme.lower() != "https":
        return False
    if _is_local_hostname(parsed.hostname):
        return False
    return True
