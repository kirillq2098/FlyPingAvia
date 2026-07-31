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
from flypingavia.version import __version__

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("flypingavia")


def _print_version() -> None:
    print(f"FlyPingAvia {__version__}")


def _handle_version_argv(argv: list[str]) -> bool:
    """Обработать --version / -V. True = выйти без запуска приложения."""
    if not argv:
        return False
    if argv[0] in ("--version", "-V"):
        _print_version()
        return True
    return False


def _log_startup_summary(settings) -> None:
    price_mode = "demo" if settings.is_demo_prices else "live"
    logger.info("FlyPingAvia version: %s", __version__)
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
    logger.info(
        "Admin health alerts: %s",
        "enabled" if settings.admin_alerts_active else "disabled",
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
    from flypingavia.monitoring.checker_job import run_checker_job

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_checker_job,
        trigger="interval",
        seconds=interval,
        id="price_check",
        max_instances=1,
        coalesce=True,
        kwargs={"checker": checker, "bot": bot, "settings": settings},
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

    from flypingavia.monitoring.loop import HealthMonitor

    health_monitor = HealthMonitor(settings, bot)
    health_monitor.start()

    async def _ensure_menu_button() -> None:
        # Не блокируем bind uvicorn/polling — иначе Docker healthcheck падает.
        # Production / стабильный HTTPS → MenuButtonWebApp; tunnel → commands (TG-05).
        from flypingavia.bot.menu_button import resolve_startup_menu_button

        menu_button = resolve_startup_menu_button(settings.telegram_webapp_url)
        if menu_button is None:
            return
        try:
            await asyncio.wait_for(
                bot.set_chat_menu_button(menu_button=menu_button),
                timeout=15,
            )
            logger.info(
                "Chat menu button: type=%s text=%s",
                getattr(menu_button, "type", None),
                getattr(menu_button, "text", None),
            )
            try:
                from flypingavia.diagnostics.miniapp_session import utc_now_iso, write_diag_event

                web = getattr(getattr(menu_button, "web_app", None), "url", None) or ""
                write_diag_event(
                    {
                        "kind": "bot",
                        "event": "bot_menu_button_state",
                        "stage": "bot_menu_button_state",
                        "ts": utc_now_iso(),
                        "menu_button_type": str(getattr(menu_button, "type", "") or "")[:32],
                        "menu_button_url": str(web)[:128],
                        "button_type": "menu_web_app",
                        "button_url": str(web)[:128],
                        "bot_username": "FlyPingAvia_Bot",
                        "polling": True,
                        "detail": "menu_button_clicks_are_not_delivered_as_bot_updates",
                    }
                )
            except Exception:
                pass
        except Exception:
            logger.exception("Не удалось установить menu button")

    menu_task = asyncio.create_task(_ensure_menu_button(), name="ensure-menu-button")

    try:
        await asyncio.gather(
            dp.start_polling(bot),
            server.serve(),
        )
    finally:
        menu_task.cancel()
        try:
            await menu_task
        except asyncio.CancelledError:
            pass
        await health_monitor.stop()
        scheduler.shutdown(wait=False)
        await bot.session.close()


def run() -> None:
    import sys

    if _handle_version_argv(sys.argv[1:]):
        return
    asyncio.run(_async_main())


if __name__ == "__main__":
    run()
