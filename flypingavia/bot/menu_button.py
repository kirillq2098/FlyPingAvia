"""Startup menu button: WebApp on stable HTTPS, commands on temporary tunnels (TG-05)."""

from __future__ import annotations

from urllib.parse import urlparse

from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from flypingavia.webapp_url import is_temporary_tunnel_hostname

MENU_BUTTON_TEXT = "FlyPing"


def telegram_webapp_button_url(webapp_url: str) -> str:
    """URL for Telegram WebAppInfo / MenuButtonWebApp.

    Canonical Settings URL strips trailing slash; Telegram menu button stores
    the root with ``/``. Keep a single form for all bot launch buttons.
    """
    url = (webapp_url or "").strip()
    if not url:
        return ""
    return url if url.endswith("/") else f"{url}/"


def resolve_startup_menu_button(
    webapp_url: str | None,
) -> MenuButtonWebApp | MenuButtonCommands | None:
    """Целевая кнопка меню для set_chat_menu_button.

    - стабильный HTTPS WEBAPP_URL → MenuButtonWebApp (текст FlyPing);
    - temporary tunnel (trycloudflare и т.п.) → MenuButtonCommands (TG-05);
    - нет URL → None (не вызывать Bot API).

    Stable production HTTPS must never fall back to MenuButtonCommands here.
    """
    url = (webapp_url or "").strip()
    if not url:
        return None
    host = urlparse(url).hostname or ""
    if is_temporary_tunnel_hostname(host):
        return MenuButtonCommands()
    button_url = telegram_webapp_button_url(url)
    return MenuButtonWebApp(
        text=MENU_BUTTON_TEXT,
        web_app=WebAppInfo(url=button_url),
    )
