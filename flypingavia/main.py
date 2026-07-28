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


async def _async_main() -> None:
    settings = get_settings()
    if not settings.bot_token or settings.bot_token == "REPLACE_ME":
        raise SystemExit(
            "Укажите BOT_TOKEN в .env (см. .env.example). Токен выдаёт @BotFather."
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
    server = uvicorn.Server(
        uvicorn.Config(
            api,
            host=settings.webapp_host,
            port=settings.webapp_port,
            log_level="info",
            loop="asyncio",
        )
    )

    logger.info(
        "FlyPingAvia started (interval=%ss, demo=%s, webapp=%s:%s, url=%s)",
        interval,
        settings.is_demo_prices,
        settings.webapp_host,
        settings.webapp_port,
        settings.webapp_url or "(не задан — кнопка Mini App скрыта)",
    )

    if settings.webapp_url:
        try:
            from aiogram.types import MenuButtonWebApp, WebAppInfo

            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Приложение",
                    web_app=WebAppInfo(url=settings.webapp_url.rstrip("/") + "/"),
                )
            )
            logger.info("Chat menu button WebApp установлен")
        except Exception:
            logger.exception("Не удалось установить menu button")

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
