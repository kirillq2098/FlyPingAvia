from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import uvicorn
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from flypingavia.api.app import create_api
from flypingavia.bot.handlers import create_dispatcher
from flypingavia.config import get_settings
from flypingavia.db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("flypingavia")


def _log_startup_summary(settings) -> None:
    price_mode = "demo" if settings.is_demo_prices else "live"
    logger.info("Environment: %s", settings.app_env)
    logger.info(
        "Mini App URL: %s",
        settings.webapp_url or "(не задан — кнопка Mini App скрыта)",
    )
    logger.info("Display timezone: %s", settings.display_timezone)
    logger.info("Price mode: %s", price_mode)
    logger.info(
        "Bind: %s:%s | Telegram WebApp: %s",
        settings.webapp_host,
        settings.webapp_port,
        settings.telegram_webapp_url or "disabled",
    )
    issues = settings.readiness_issues()
    if issues:
        level = logging.ERROR if settings.is_production else logging.WARNING
        logger.log(
            level,
            "Readiness issues (%s): %s",
            settings.app_env,
            ", ".join(issues),
        )


async def _async_main() -> None:
    settings = get_settings()
    if not settings.bot_token or settings.bot_token == "REPLACE_ME":
        raise SystemExit(
            "Укажите BOT_TOKEN в .env (см. .env.example). Токен выдаёт @BotFather."
        )

    if settings.is_production and not settings.webapp_url:
        raise SystemExit(
            "APP_ENV=production требует WEBAPP_URL=https://… "
            "(постоянный HTTPS, не temporary tunnel)."
        )

    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    await init_db()

    from flypingavia.services.locations import get_location_directory

    try:
        await get_location_directory().ensure_loaded()
        logger.info("Справочник городов загружен")
    except Exception:
        logger.exception("Не удалось загрузить справочник городов")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp, checker = create_dispatcher(settings, bot)

    interval = settings.poll_interval_seconds
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        checker.run_once,
        trigger="interval",
        seconds=interval,
        id="price_check",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()

    api = create_api(settings)
    # Proxy headers: только с доверенных IP reverse proxy (по умолчанию loopback).
    # Не используйте forwarded_allow_ips="*" при публичном bind.
    server = uvicorn.Server(
        uvicorn.Config(
            api,
            host=settings.webapp_host,
            port=settings.webapp_port,
            log_level="info",
            loop="asyncio",
            proxy_headers=True,
            forwarded_allow_ips=settings.forwarded_allow_ips,
        )
    )

    _log_startup_summary(settings)
    logger.info("Price check interval=%ss", interval)

    if settings.telegram_webapp_url:
        # Menu button в Telegram часто кэширует старый tunnel URL (Error 1033).
        # Надёжнее обновлять WebApp через reply/inline-кнопки после /start.
        try:
            from aiogram.types import MenuButtonCommands

            await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
            logger.info("Chat menu button сброшен в commands (WebApp — через /start)")
        except Exception:
            logger.exception("Не удалось сбросить menu button")

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
        )
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def run() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
