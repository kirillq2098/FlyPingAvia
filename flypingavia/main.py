from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler

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

    # Гарантируем каталог для SQLite
    if settings.database_url.startswith("sqlite"):
        db_path = settings.database_url.split("///")[-1]
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    await init_db()

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
    logger.info(
        "FlyPingAvia v0.1.0 started (interval=%ss, demo=%s, currency=%s)",
        interval,
        settings.is_demo_prices,
        settings.currency.upper(),
    )

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


def run() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
