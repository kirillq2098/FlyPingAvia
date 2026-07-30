"""RL-03: отправка служебных алертов администратору (без рекурсии)."""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.enums import ParseMode

from flypingavia.config import Settings

logger = logging.getLogger(__name__)


def admin_alerts_configured(settings: Settings) -> bool:
    return bool(settings.admin_alerts_enabled and settings.admin_telegram_chat_id is not None)


async def send_admin_alert(
    bot: Bot,
    *,
    chat_id: int | None,
    text: str,
    enabled: bool = True,
) -> bool:
    """Отправить HTML-сообщение админу. Ошибки не пробрасываются и не создают incident."""
    if not enabled or chat_id is None:
        return False
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        return True
    except Exception:
        # Не логируем chat_id на info; без recursive incident.
        logger.warning("Admin health alert delivery failed", exc_info=True)
        return False


async def maybe_send_admin_alert(
    bot: Bot,
    settings: Settings,
    *,
    text: str,
) -> bool:
    if not admin_alerts_configured(settings):
        return False
    return await send_admin_alert(
        bot,
        chat_id=settings.admin_telegram_chat_id,
        text=text,
        enabled=True,
    )
