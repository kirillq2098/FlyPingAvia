from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

from flypingavia.bot import formatters as fmt
from flypingavia.bot import keyboards as kb
from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services.checker import PriceChecker
from flypingavia.services.prices import (
    PriceProvider,
    build_affiliate_url,
    build_price_provider,
)


class AddWatch(StatesGroup):
    origin = State()
    destination = State()
    depart_date = State()
    custom_price = State()


def _parse_iata(value: str) -> str | None:
    raw = value.strip().upper()
    if re.fullmatch(r"[A-Z]{3}", raw):
        return raw
    return None


def _parse_date(value: str) -> date | None:
    raw = value.strip()
    for pattern in ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y"):
        try:
            return datetime.strptime(raw, pattern).date()
        except ValueError:
            continue
    return None


def _parse_price(value: str) -> float | None:
    try:
        price = float(value.replace(",", ".").replace(" ", "").replace("₽", ""))
    except ValueError:
        return None
    return price


async def _ensure_user(message_or_user) -> None:
    user = message_or_user if hasattr(message_or_user, "id") else message_or_user.from_user
    async with session_scope() as session:
        await repo.get_or_create_user(session, telegram_id=user.id, username=user.username)


async def _show_route_preview(
    message: Message,
    settings: Settings,
    provider: PriceProvider,
    state: FSMContext,
    origin: str,
    destination: str,
    depart_date: Optional[date],
) -> None:
    wait = await message.answer("Считаю вилку цен…", reply_markup=kb.main_menu())
    quote = await provider.get_cheapest(origin, destination, depart_date, settings.currency)
    band = await provider.get_price_band(origin, destination, depart_date, settings.currency)

    draft_id = f"{origin}{destination}{depart_date.isoformat() if depart_date else 'any'}"
    await state.update_data(
        origin=origin,
        destination=destination,
        depart_date=depart_date.isoformat() if depart_date else None,
        draft_id=draft_id,
        cheap=int(band.cheap_max) if band else None,
        typical=int(band.typical) if band else None,
    )

    text = fmt.format_price_card(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        quote=quote,
        band=band,
        title="Выберите порог слежения",
    )
    text += "\n\nНажмите кнопку вилки или введите свою цену."

    markup = None
    if band is not None:
        markup = kb.threshold_kb(draft_id, int(band.cheap_max), int(band.typical))

    try:
        await wait.edit_text(text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        await message.answer(text, parse_mode="HTML", reply_markup=markup, disable_web_page_preview=True)

    if band is None:
        await state.set_state(AddWatch.custom_price)
        await message.answer(
            "Не удалось посчитать вилку. Введите порог числом, например <code>12000</code>",
            parse_mode="HTML",
            reply_markup=kb.cancel_kb(),
        )


async def _create_watch(
    *,
    telegram_id: int,
    username: Optional[str],
    settings: Settings,
    origin: str,
    destination: str,
    depart_date: Optional[date],
    max_price: float,
) -> tuple[int, str]:
    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=telegram_id, username=username)
        watch = await repo.add_watch(
            session,
            user=user,
            origin=origin,
            destination=destination,
            max_price=max_price,
            depart_date=depart_date,
            currency=settings.currency,
        )
        return watch.id, watch.route_label


def create_router(settings: Settings, checker: PriceChecker, provider: PriceProvider) -> Router:
    router = Router(name="main")

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await _ensure_user(message)
        await message.answer(fmt.welcome_text(), parse_mode="HTML", reply_markup=kb.main_menu())
        await message.answer("Популярные направления:", reply_markup=kb.popular_routes_kb())

    @router.message(Command("help"))
    @router.message(F.text == "ℹ️ Помощь")
    async def cmd_help(message: Message) -> None:
        await message.answer(fmt.help_text(), parse_mode="HTML", reply_markup=kb.main_menu())

    @router.message(F.text == "❌ Отмена")
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Отменил. Можно начать снова.", reply_markup=kb.main_menu())

    @router.message(Command("add"))
    @router.message(F.text == "➕ Добавить")
    @router.callback_query(F.data == "menu:add")
    async def start_add(event: Message | CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(AddWatch.origin)
        text = (
            "Откуда летим?\n"
            "Введите IATA-код, например <code>MOW</code> или <code>LED</code>"
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb.cancel_kb())
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb.cancel_kb())

    @router.callback_query(F.data.startswith("quick:"))
    async def quick_route(callback: CallbackQuery, state: FSMContext) -> None:
        _, origin, destination = callback.data.split(":")
        await state.clear()
        await state.set_state(AddWatch.depart_date)
        await state.update_data(origin=origin, destination=destination)
        await callback.answer()
        await callback.message.answer(
            f"Маршрут <b>{origin} → {destination}</b>\n"
            "Введите дату вылета (<code>2026-09-10</code> или <code>10.09.2026</code>)\n"
            "или нажмите «Любая дата».",
            parse_mode="HTML",
            reply_markup=kb.skip_date_kb(),
        )

    @router.message(AddWatch.origin)
    async def add_origin(message: Message, state: FSMContext) -> None:
        origin = _parse_iata(message.text or "")
        if not origin:
            await message.answer("Нужен код из 3 латинских букв, например MOW.")
            return
        await state.update_data(origin=origin)
        await state.set_state(AddWatch.destination)
        await message.answer(
            f"Откуда: <b>{origin}</b>\nКуда летим? Например <code>AYT</code>",
            parse_mode="HTML",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(AddWatch.destination)
    async def add_destination(message: Message, state: FSMContext) -> None:
        destination = _parse_iata(message.text or "")
        if not destination:
            await message.answer("Нужен код из 3 латинских букв, например AYT.")
            return
        await state.update_data(destination=destination)
        await state.set_state(AddWatch.depart_date)
        data = await state.get_data()
        await message.answer(
            f"Маршрут <b>{data['origin']} → {destination}</b>\n"
            "Введите дату вылета или нажмите «Любая дата».",
            parse_mode="HTML",
            reply_markup=kb.skip_date_kb(),
        )

    @router.message(AddWatch.depart_date, F.text == "📅 Любая дата")
    async def add_any_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        await _show_route_preview(
            message,
            settings,
            provider,
            state,
            data["origin"],
            data["destination"],
            None,
        )

    @router.message(AddWatch.depart_date)
    async def add_date(message: Message, state: FSMContext) -> None:
        depart_date = _parse_date(message.text or "")
        if depart_date is None:
            await message.answer(
                "Дата в формате <code>2026-09-10</code> или <code>10.09.2026</code>",
                parse_mode="HTML",
            )
            return
        data = await state.get_data()
        await _show_route_preview(
            message,
            settings,
            provider,
            state,
            data["origin"],
            data["destination"],
            depart_date,
        )

    @router.callback_query(F.data.startswith("thr:"))
    async def choose_threshold(callback: CallbackQuery, state: FSMContext) -> None:
        # thr:{draft_id}:{kind}:{price}
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer("Ошибка кнопки", show_alert=True)
            return
        _, draft_id, kind, price_raw = parts[0], parts[1], parts[2], parts[3]
        data = await state.get_data()
        if data.get("draft_id") != draft_id and data.get("origin"):
            # draft мог устареть — всё равно берём данные из state
            pass
        if not data.get("origin"):
            await callback.answer("Сессия истекла — нажмите ➕ Добавить", show_alert=True)
            return

        if kind == "custom":
            await state.set_state(AddWatch.custom_price)
            await callback.answer()
            await callback.message.answer(
                "Введите свою цену-порог числом, например <code>13500</code>",
                parse_mode="HTML",
                reply_markup=kb.cancel_kb(),
            )
            return

        max_price = float(price_raw)
        depart_date = date.fromisoformat(data["depart_date"]) if data.get("depart_date") else None
        watch_id, _ = await _create_watch(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            settings=settings,
            origin=data["origin"],
            destination=data["destination"],
            depart_date=depart_date,
            max_price=max_price,
        )
        await state.clear()

        quote = await provider.get_cheapest(
            data["origin"], data["destination"], depart_date, settings.currency
        )
        band = await provider.get_price_band(
            data["origin"], data["destination"], depart_date, settings.currency
        )
        link = build_affiliate_url(
            data["origin"], data["destination"], settings.affiliate_marker, depart_date
        )
        text = fmt.format_price_card(
            origin=data["origin"],
            destination=data["destination"],
            depart_date=depart_date,
            quote=quote,
            band=band,
            threshold=max_price,
            title="Подписка создана",
            watch_id=watch_id,
        )
        await callback.answer("Готово")
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.after_watch_kb(watch_id, link),
            disable_web_page_preview=True,
        )
        await callback.message.answer("Главное меню:", reply_markup=kb.main_menu())

    @router.message(AddWatch.custom_price)
    async def add_custom_price(message: Message, state: FSMContext) -> None:
        max_price = _parse_price(message.text or "")
        if max_price is None:
            await message.answer("Введите число, например 12000.")
            return
        data = await state.get_data()
        if not data.get("origin"):
            await state.clear()
            await message.answer("Сессия истекла. Нажмите ➕ Добавить", reply_markup=kb.main_menu())
            return
        depart_date = date.fromisoformat(data["depart_date"]) if data.get("depart_date") else None
        watch_id, _ = await _create_watch(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            settings=settings,
            origin=data["origin"],
            destination=data["destination"],
            depart_date=depart_date,
            max_price=max_price,
        )
        await state.clear()
        quote = await provider.get_cheapest(
            data["origin"], data["destination"], depart_date, settings.currency
        )
        band = await provider.get_price_band(
            data["origin"], data["destination"], depart_date, settings.currency
        )
        link = build_affiliate_url(
            data["origin"], data["destination"], settings.affiliate_marker, depart_date
        )
        text = fmt.format_price_card(
            origin=data["origin"],
            destination=data["destination"],
            depart_date=depart_date,
            quote=quote,
            band=band,
            threshold=max_price,
            title="Подписка создана",
            watch_id=watch_id,
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.after_watch_kb(watch_id, link),
            disable_web_page_preview=True,
        )
        await message.answer("Главное меню:", reply_markup=kb.main_menu())

    @router.message(Command("watch"))
    async def cmd_watch(message: Message, command: CommandObject, state: FSMContext) -> None:
        parts = (command.args or "").split()
        if len(parts) < 2:
            await start_add(message, state)
            return

        origin = _parse_iata(parts[0])
        destination = _parse_iata(parts[1])
        if not origin or not destination:
            await message.answer("Коды аэропортов: 3 латинские буквы, например MOW AYT.")
            return

        max_price = None
        depart_date = None
        if len(parts) >= 3:
            # цена или дата
            maybe_price = _parse_price(parts[2])
            maybe_date = _parse_date(parts[2])
            if maybe_date and maybe_price is None:
                depart_date = maybe_date
            elif maybe_price is not None:
                max_price = maybe_price
            else:
                await message.answer("Третий аргумент — цена или дата.")
                return
        if len(parts) >= 4:
            depart_date = _parse_date(parts[3]) or depart_date
            if max_price is None:
                max_price = _parse_price(parts[3])

        await state.clear()
        await state.set_state(AddWatch.depart_date)
        await state.update_data(origin=origin, destination=destination)
        if max_price is not None:
            # сразу создаём с ценой
            await state.clear()
            watch_id, _ = await _create_watch(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                settings=settings,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                max_price=max_price,
            )
            quote = await provider.get_cheapest(origin, destination, depart_date, settings.currency)
            band = await provider.get_price_band(origin, destination, depart_date, settings.currency)
            link = build_affiliate_url(origin, destination, settings.affiliate_marker, depart_date)
            text = fmt.format_price_card(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                quote=quote,
                band=band,
                threshold=max_price,
                title="Подписка создана",
                watch_id=watch_id,
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.after_watch_kb(watch_id, link),
                disable_web_page_preview=True,
            )
            return

        # без цены — показать вилку
        if depart_date is not None:
            await _show_route_preview(message, settings, provider, state, origin, destination, depart_date)
        else:
            await state.set_state(AddWatch.depart_date)
            await message.answer(
                f"Маршрут <b>{origin} → {destination}</b>\n"
                "Введите дату или нажмите «Любая дата».",
                parse_mode="HTML",
                reply_markup=kb.skip_date_kb(),
            )

    @router.message(Command("list"))
    @router.message(F.text == "📋 Мои маршруты")
    @router.callback_query(F.data == "menu:list")
    async def cmd_list(event: Message | CallbackQuery) -> None:
        user = event.from_user
        if isinstance(event, CallbackQuery):
            await event.answer()
            message = event.message
        else:
            message = event

        async with session_scope() as session:
            db_user = await repo.get_or_create_user(session, telegram_id=user.id, username=user.username)
            watches = list(await repo.list_watches(session, db_user.id))

        if not watches:
            await message.answer(
                "Подписок пока нет.\nДобавьте маршрут — покажу вилку цен и помогу выбрать порог.",
                reply_markup=kb.list_empty_kb(),
            )
            return

        await message.answer(f"Ваши маршруты: <b>{len(watches)}</b>", parse_mode="HTML", reply_markup=kb.main_menu())
        for w in watches:
            quote = None
            band = None
            try:
                quote = await provider.get_cheapest(w.origin, w.destination, w.depart_date, w.currency.lower())
                band = await provider.get_price_band(w.origin, w.destination, w.depart_date, w.currency.lower())
            except Exception:
                pass
            if quote is None and w.last_price is not None:
                from flypingavia.services.prices import PriceQuote

                quote = PriceQuote(price=w.last_price, currency=w.currency, source="cache")
            link = build_affiliate_url(w.origin, w.destination, settings.affiliate_marker, w.depart_date)
            text = fmt.format_price_card(
                origin=w.origin,
                destination=w.destination,
                depart_date=w.depart_date,
                quote=quote,
                band=band,
                threshold=w.max_price,
                watch_id=w.id,
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.watch_actions_kb(w.id, link),
                disable_web_page_preview=True,
            )

    @router.message(Command("unwatch"))
    async def cmd_unwatch(message: Message, command: CommandObject) -> None:
        args = (command.args or "").strip()
        if not args.isdigit():
            await message.answer("Формат: /unwatch ID\nИли удалите кнопкой в «Мои маршруты».")
            return
        watch_id = int(args)
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session, telegram_id=message.from_user.id, username=message.from_user.username
            )
            ok = await repo.deactivate_watch(session, user.id, watch_id)
        await message.answer(
            f"Подписка #{watch_id} удалена." if ok else "Не нашёл такую подписку.",
            reply_markup=kb.main_menu(),
        )

    @router.callback_query(F.data.startswith("wdel:"))
    async def cb_delete(callback: CallbackQuery) -> None:
        watch_id = int(callback.data.split(":")[1])
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session, telegram_id=callback.from_user.id, username=callback.from_user.username
            )
            ok = await repo.deactivate_watch(session, user.id, watch_id)
        await callback.answer("Удалено" if ok else "Не найдено")
        if ok:
            await callback.message.edit_text(f"🗑 Подписка #{watch_id} удалена.")

    @router.callback_query(F.data.startswith("wcheck:"))
    async def cb_check_one(callback: CallbackQuery) -> None:
        watch_id = int(callback.data.split(":")[1])
        await callback.answer("Обновляю…")
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session, telegram_id=callback.from_user.id, username=callback.from_user.username
            )
            watches = await repo.list_watches(session, user.id)
            watch = next((w for w in watches if w.id == watch_id), None)
            if watch is None:
                await callback.message.answer("Подписка не найдена.")
                return
            # detach fields
            origin, destination, depart_date, max_price, currency = (
                watch.origin,
                watch.destination,
                watch.depart_date,
                watch.max_price,
                watch.currency,
            )

        quote = await provider.get_cheapest(origin, destination, depart_date, currency.lower())
        band = await provider.get_price_band(origin, destination, depart_date, currency.lower())
        if quote is not None:
            async with session_scope() as session:
                from flypingavia.db.models import Watch
                from datetime import datetime, timezone

                fresh = await session.get(Watch, watch_id)
                if fresh:
                    fresh.last_price = quote.price
                    fresh.last_checked_at = datetime.now(timezone.utc)

        link = build_affiliate_url(origin, destination, settings.affiliate_marker, depart_date)
        text = fmt.format_price_card(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            quote=quote,
            band=band,
            threshold=max_price,
            title="Актуальная цена",
            watch_id=watch_id,
        )
        await callback.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.watch_actions_kb(watch_id, link),
            disable_web_page_preview=True,
        )

    @router.message(Command("check"))
    @router.message(F.text == "🔄 Проверить цены")
    async def cmd_check(message: Message) -> None:
        await message.answer("Проверяю все маршруты…", reply_markup=kb.main_menu())
        alerts = await checker.run_once()
        async with session_scope() as session:
            user = await repo.get_or_create_user(
                session, telegram_id=message.from_user.id, username=message.from_user.username
            )
            watches = list(await repo.list_watches(session, user.id))

        if not watches:
            await message.answer("Нет активных подписок.", reply_markup=kb.list_empty_kb())
            return

        for w in watches:
            try:
                quote = await provider.get_cheapest(w.origin, w.destination, w.depart_date, w.currency.lower())
                band = await provider.get_price_band(w.origin, w.destination, w.depart_date, w.currency.lower())
            except Exception:
                await message.answer(f"#{w.id} {w.origin} → {w.destination}: ошибка запроса")
                continue
            link = build_affiliate_url(w.origin, w.destination, settings.affiliate_marker, w.depart_date)
            text = fmt.format_price_card(
                origin=w.origin,
                destination=w.destination,
                depart_date=w.depart_date,
                quote=quote,
                band=band,
                threshold=w.max_price,
                watch_id=w.id,
            )
            await message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.watch_actions_kb(w.id, link),
                disable_web_page_preview=True,
            )

        if alerts:
            await message.answer(f"Алертов отправлено: {alerts}")

    @router.message(StateFilter(None), F.text)
    async def fallback(message: Message) -> None:
        await message.answer(
            "Выберите действие на клавиатуре или нажмите ℹ️ Помощь",
            reply_markup=kb.main_menu(),
        )

    return router


def create_dispatcher(settings: Settings, bot: Bot) -> tuple[Dispatcher, PriceChecker]:
    provider = build_price_provider(settings)
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(create_router(settings, checker, provider))
    return dp, checker
