from __future__ import annotations

import re
from datetime import date, datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import build_affiliate_url, build_price_provider

HELP_TEXT = (
    "<b>FlyPingAvia</b> — монитор цен на авиабилеты.\n\n"
    "<b>Команды</b>\n"
    "/watch MOW IST 15000 [YYYY-MM-DD] — следить за маршрутом\n"
    "/list — ваши подписки\n"
    "/unwatch ID — удалить подписку\n"
    "/check — проверить цены сейчас\n"
    "/help — справка\n\n"
    "Пример:\n"
    "<code>/watch MOW AYT 12000 2026-09-10</code>\n"
    "Без даты бот ищет минимальную цену на ближайший год."
)


def _parse_iata(value: str) -> str | None:
    raw = value.strip().upper()
    # Простая транслитерация популярных русских кодов не нужна — ждём IATA латиницей
    if re.fullmatch(r"[A-Z]{3}", raw):
        return raw
    return None


def _parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def create_router(settings: Settings, checker: PriceChecker) -> Router:
    router = Router(name="main")

    @router.message(CommandStart())
    async def cmd_start(message: Message) -> None:
        async with session_scope() as session:
            await repo.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
        mode = "demo-цены" if settings.is_demo_prices else "Travelpayouts API"
        await message.answer(
            f"Привет! Я слежу за ценами на авиабилеты и пишу, когда стало дешевле.\n"
            f"Режим цен: <b>{mode}</b>\n\n"
            f"{HELP_TEXT}",
            parse_mode="HTML",
        )

    @router.message(Command("help"))
    async def cmd_help(message: Message) -> None:
        await message.answer(HELP_TEXT, parse_mode="HTML")

    @router.message(Command("watch"))
    async def cmd_watch(message: Message, command: CommandObject) -> None:
        parts = (command.args or "").split()
        if len(parts) < 3:
            await message.answer(
                "Формат: /watch ORIGIN DEST MAX_PRICE [YYYY-MM-DD]\n"
                "Пример: /watch MOW IST 15000 2026-08-20"
            )
            return

        origin = _parse_iata(parts[0])
        destination = _parse_iata(parts[1])
        if not origin or not destination:
            await message.answer("Коды аэропортов должны быть IATA из 3 латинских букв (MOW, IST, AYT).")
            return

        try:
            max_price = float(parts[2].replace(",", ".").replace(" ", ""))
        except ValueError:
            await message.answer("Цена должна быть числом, например 15000.")
            return

        depart_date = None
        if len(parts) >= 4:
            depart_date = _parse_date(parts[3])
            if depart_date is None:
                await message.answer("Дата в формате YYYY-MM-DD, например 2026-09-10.")
                return

        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            watch = await repo.add_watch(
                session,
                user=user,
                origin=origin,
                destination=destination,
                max_price=max_price,
                depart_date=depart_date,
                currency=settings.currency,
            )

            watch_id = watch.id
            label = watch.route_label

        link = build_affiliate_url(
            origin=origin,
            destination=destination,
            marker=settings.affiliate_marker,
            depart_date=depart_date,
        )
        await message.answer(
            f"✅ Подписка #{watch_id}: {label}\n"
            f"Порог: {int(max_price)} {settings.currency.upper()}\n"
            f'<a href="{link}">Открыть поиск</a>\n\n'
            "Проверка идёт по расписанию; /check — прямо сейчас.",
            parse_mode="HTML",
            disable_web_page_preview=True,
        )

    @router.message(Command("list"))
    async def cmd_list(message: Message) -> None:
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            watches = await repo.list_watches(session, user.id)
            rows = []
            for w in watches:
                last = (
                    f"{int(w.last_price)} {w.currency}"
                    if w.last_price is not None
                    else "ещё не проверяли"
                )
                rows.append(
                    f"#{w.id} {w.route_label}\n"
                    f"   порог {int(w.max_price)} {w.currency}, сейчас: {last}"
                )

        if not rows:
            await message.answer("Подписок пока нет. Добавьте: /watch MOW AYT 12000")
            return
        await message.answer("Ваши маршруты:\n\n" + "\n\n".join(rows))

    @router.message(Command("unwatch"))
    async def cmd_unwatch(message: Message, command: CommandObject) -> None:
        args = (command.args or "").strip()
        if not args.isdigit():
            await message.answer("Формат: /unwatch ID\nID смотрите в /list")
            return
        watch_id = int(args)
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            ok = await repo.deactivate_watch(session, user.id, watch_id)

        if ok:
            await message.answer(f"Подписка #{watch_id} удалена.")
        else:
            await message.answer("Не нашёл активную подписку с таким ID.")

    @router.message(Command("check"))
    async def cmd_check(message: Message) -> None:
        await message.answer("Проверяю цены…")
        alerts = await checker.run_once()
        # Также покажем актуальные цены по своим подпискам
        provider = build_price_provider(settings)
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session,
                telegram_id=message.from_user.id,
                username=message.from_user.username,
            )
            watches = list(await repo.list_watches(session, user.id))

        if not watches:
            await message.answer("Нет активных подписок.")
            return

        lines: list[str] = []
        for w in watches:
            try:
                quote = await provider.get_cheapest(
                    w.origin, w.destination, w.depart_date, w.currency.lower()
                )
            except Exception:
                lines.append(f"#{w.id} {w.route_label}: ошибка запроса")
                continue
            if quote is None:
                lines.append(f"#{w.id} {w.route_label}: цена не найдена")
                continue
            mark = "✅" if quote.price <= w.max_price else "⏳"
            lines.append(
                f"{mark} #{w.id} {w.route_label}: "
                f"{int(quote.price)} {quote.currency} (порог {int(w.max_price)})"
            )

        suffix = f"\n\nАлертов отправлено: {alerts}" if alerts else ""
        await message.answer("Результат проверки:\n" + "\n".join(lines) + suffix)

    @router.message(F.text)
    async def fallback(message: Message) -> None:
        await message.answer("Не понял команду. Смотрите /help")

    return router


def create_dispatcher(settings: Settings, bot: Bot) -> tuple[Dispatcher, PriceChecker]:
    provider = build_price_provider(settings)
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)
    dp = Dispatcher()
    dp.include_router(create_router(settings, checker))
    return dp, checker
