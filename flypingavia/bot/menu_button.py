"""Startup menu button: WebApp on stable HTTPS, commands on temporary tunnels (TG-05)."""

from __future__ import annotations

from urllib.parse import urlparse

from aiogram.types import MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from flypingavia.webapp_url import is_temporary_tunnel_hostname

MENU_BUTTON_TEXT = "FlyPing"


def resolve_startup_menu_button(
    webapp_url: str | None,
) -> MenuButtonWebApp | MenuButtonCommands | None:
    """Целевая кнопка меню для set_chat_menu_button.

    - стабильный HTTPS WEBAPP_URL → MenuButtonWebApp (текст FlyPing);
    - temporary tunnel (trycloudflare и т.п.) → MenuButtonCommands (TG-05);
    - нет URL → None (не вызывать Bot API).
    """
    url = (webapp_url or "").strip()
    if not url:
        return None
    host = urlparse(url).hostname or ""
    if is_temporary_tunnel_hostname(host):
        return MenuButtonCommands()
    return MenuButtonWebApp(
        text=MENU_BUTTON_TEXT,
        web_app=WebAppInfo(url=url),
    )
