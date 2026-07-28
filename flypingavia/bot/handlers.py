from __future__ import annotations

import re
from datetime import date, datetime, timezone
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
from flypingavia.db.models import Watch
from flypingavia.db.session import session_scope
from flypingavia.services.checker import PriceChecker
from flypingavia.services.locations import Place, get_location_directory, resolve_place
from flypingavia.services.prices import (
    PriceProvider,
    PriceQuote,
    build_affiliate_url,
    build_price_provider,
)


class AddWatch(StatesGroup):
    origin = State()
    destination = State()
    depart_date = State()
    custom_price = State()


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
        return float(value.replace(",", ".").replace(" ", "").replace("₽", ""))
    except ValueError:
        return None


def _place_payload(place: Place) -> dict:
    return {
        "code": place.code,
        "name": place.name,
        "kind": place.kind,
        "search": ",".join(place.search_codes),
        "airports": list(place.airport_codes),
    }


def _place_from_data(prefix: str, data: dict) -> Optional[Place]:
    code = data.get(f"{prefix}_code") or data.get(prefix)
    if not code:
        return None
    search = data.get(f"{prefix}_search") or code
    airports = tuple(c for c in str(search).split(",") if c)
    return Place(
        code=code,
        name=data.get(f"{prefix}_name") or code,
        kind=data.get(f"{prefix}_kind") or "city",
        airport_codes=airports if len(airports) > 1 or airports != (code,) else airports,
        airport_names=(),
    )


async def _ensure_user(message_or_user) -> None:
    user = message_or_user if hasattr(message_or_user, "id") else message_or_user.from_user
    async with session_scope() as session:
        await repo.get_or_create_user(session, telegram_id=user.id, username=user.username)


async def _ask_place_choice(
    message: Message,
    places: list[Place],
    *,
    prefix: str,
    title: str,
) -> None:
    await message.answer(
        f"{title}\nВыберите вариант:",
        reply_markup=kb.places_kb(prefix, places),
    )


async def _fetch_quote_band(
    provider: PriceProvider,
    origin: Place,
    destination: Place,
    depart_date: Optional[date],
    currency: str,
):
    quote = await provider.get_cheapest_across(
        origin.search_codes,
        destination.search_codes,
        depart_date,
        currency,
    )
    # Вилку считаем по основному коду города — быстрее и стабильнее
    band = await provider.get_price_band(origin.code, destination.code, depart_date, currency)
    return quote, band


def _airport_note(origin: Place, destination: Place) -> Optional[str]:
    notes = []
    if origin.kind == "city" and len(origin.airport_codes) > 1:
        notes.append(f"Аэропорты вылета: {', '.join(origin.airport_codes)} — беру самый дешёвый")
    if destination.kind == "city" and len(destination.airport_codes) > 1:
        notes.append(f"Аэропорты прилёта: {', '.join(destination.airport_codes)} — беру самый дешёвый")
    return "\n".join(notes) if notes else None


async def _show_route_preview(
    message: Message,
    settings: Settings,
    provider: PriceProvider,
    state: FSMContext,
    origin: Place,
    destination: Place,
    depart_date: Optional[date],
) -> None:
    wait = await message.answer("Ищу по аэропортам и считаю вилку…", reply_markup=menu())
    quote, band = await _fetch_quote_band(
        provider, origin, destination, depart_date, settings.currency
    )

    draft_id = f"{origin.code}{destination.code}{depart_date.isoformat() if depart_date else 'any'}"
    await state.update_data(
        origin_code=origin.code,
        origin_name=origin.name,
        origin_kind=origin.kind,
        origin_search=",".join(origin.search_codes),
        destination_code=destination.code,
        destination_name=destination.name,
        destination_kind=destination.kind,
        destination_search=",".join(destination.search_codes),
        depart_date=depart_date.isoformat() if depart_date else None,
        draft_id=draft_id,
    )

    text = fmt.format_price_card(
        origin=origin.code,
        destination=destination.code,
        depart_date=depart_date,
        quote=quote,
        band=band,
        title="Выберите порог слежения",
        origin_name=origin.name,
        destination_name=destination.name,
        airport_note=_airport_note(origin, destination),
    )
    text += "\n\nНажмите кнопку вилки или введите свою цену."

    markup = kb.threshold_kb(draft_id, int(band.cheap_max), int(band.typical)) if band else None
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


async def _create_watch_from_state(
    *,
    telegram_id: int,
    username: Optional[str],
    settings: Settings,
    data: dict,
    max_price: float,
) -> int:
    depart_date = date.fromisoformat(data["depart_date"]) if data.get("depart_date") else None
    async with session_scope() as session:
        user = await repo.get_or_create_user(session, telegram_id=telegram_id, username=username)
        watch = await repo.add_watch(
            session,
            user=user,
            origin=data["origin_code"],
            destination=data["destination_code"],
            origin_name=data.get("origin_name"),
            destination_name=data.get("destination_name"),
            origin_search=data.get("origin_search"),
            destination_search=data.get("destination_search"),
            max_price=max_price,
            depart_date=depart_date,
            currency=settings.currency,
        )
        return watch.id


async def _confirm_watch_message(
    target: Message,
    settings: Settings,
    provider: PriceProvider,
    data: dict,
    watch_id: int,
    max_price: float,
) -> None:
    origin = _place_from_data("origin", data)
    destination = _place_from_data("destination", data)
    assert origin and destination
    depart_date = date.fromisoformat(data["depart_date"]) if data.get("depart_date") else None
    quote, band = await _fetch_quote_band(
        provider, origin, destination, depart_date, settings.currency
    )
    link = build_affiliate_url(
        origin.code, destination.code, settings.affiliate_marker, depart_date
    )
    text = fmt.format_price_card(
        origin=origin.code,
        destination=destination.code,
        depart_date=depart_date,
        quote=quote,
        band=band,
        threshold=max_price,
        title="Подписка создана",
        watch_id=watch_id,
        origin_name=origin.name,
        destination_name=destination.name,
        airport_note=_airport_note(origin, destination),
    )
    await target.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb.after_watch_kb(watch_id, link),
        disable_web_page_preview=True,
    )
    await target.answer("Главное меню:", reply_markup=menu())


def create_router(settings: Settings, checker: PriceChecker, provider: PriceProvider) -> Router:
    router = Router(name="main")
    webapp = (settings.webapp_url or "").strip() or None

    def menu():
        return kb.main_menu(webapp)

    @router.message(CommandStart())
    async def cmd_start(message: Message, state: FSMContext) -> None:
        await state.clear()
        await _ensure_user(message)
        await get_location_directory().ensure_loaded()
        await message.answer(fmt.welcome_text(), parse_mode="HTML", reply_markup=menu())
        app_kb = kb.open_app_kb(webapp)
        if app_kb and webapp:
            from urllib.parse import urlparse

            host = urlparse(webapp).hostname or webapp
            await message.answer(
                "Приложение внутри Telegram:\n\n"
                "Если на телефоне не открывается — один раз укажите домен в @BotFather:\n"
                "1. Откройте @BotFather → /mybots → ваш бот\n"
                "2. Bot Settings → Domain\n"
                f"3. Вставьте: <code>{host}</code>\n\n"
                "Либо откройте через кнопку «в браузере».",
                parse_mode="HTML",
                reply_markup=app_kb,
            )
        await message.answer("Популярные направления:", reply_markup=kb.popular_routes_kb())

    @router.message(Command("help"))
    @router.message(F.text == "ℹ️ Помощь")
    async def cmd_help(message: Message) -> None:
        await message.answer(fmt.help_text(), parse_mode="HTML", reply_markup=menu())

    @router.message(F.text == "❌ Отмена")
    async def cmd_cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Отменил. Можно начать снова.", reply_markup=menu())

    @router.message(Command("add"))
    @router.message(F.text == "➕ Добавить")
    @router.callback_query(F.data == "menu:add")
    async def start_add(event: Message | CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(AddWatch.origin)
        await get_location_directory().ensure_loaded()
        text = (
            "Откуда летим?\n"
            "Напишите <b>город</b> или код: <code>Москва</code>, <code>MOW</code>, <code>Шереметьево</code>"
        )
        if isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb.cancel_kb())
        else:
            await event.answer(text, parse_mode="HTML", reply_markup=kb.cancel_kb())

    async def _set_origin_and_ask_dest(message: Message, state: FSMContext, place: Place) -> None:
        payload = _place_payload(place)
        await state.update_data(
            origin_code=payload["code"],
            origin_name=payload["name"],
            origin_kind=payload["kind"],
            origin_search=payload["search"],
        )
        await state.set_state(AddWatch.destination)
        extra = ""
        if place.kind == "city" and len(place.airport_codes) > 1:
            extra = f"\nАэропорты: {', '.join(place.airport_codes)} — выберу самый дешёвый"
        await message.answer(
            f"Откуда: <b>{place.short_label}</b>{extra}\n\n"
            "Куда летим? Город или код, например <code>Анталья</code> / <code>AYT</code>",
            parse_mode="HTML",
            reply_markup=kb.cancel_kb(),
        )

    async def _set_dest_and_ask_date(message: Message, state: FSMContext, place: Place) -> None:
        payload = _place_payload(place)
        await state.update_data(
            destination_code=payload["code"],
            destination_name=payload["name"],
            destination_kind=payload["kind"],
            destination_search=payload["search"],
        )
        await state.set_state(AddWatch.depart_date)
        data = await state.get_data()
        extra = ""
        if place.kind == "city" and len(place.airport_codes) > 1:
            extra = f"\nАэропорты прилёта: {', '.join(place.airport_codes)}"
        await message.answer(
            f"Маршрут <b>{data.get('origin_name')} ({data.get('origin_code')}) → {place.short_label}</b>"
            f"{extra}\n\n"
            "Введите дату вылета (<code>10.09.2026</code>) или нажмите «Любая дата».",
            parse_mode="HTML",
            reply_markup=kb.skip_date_kb(),
        )

    @router.callback_query(F.data.startswith("quick:"))
    async def quick_route(callback: CallbackQuery, state: FSMContext) -> None:
        _, origin_code, destination_code = callback.data.split(":")
        await get_location_directory().ensure_loaded()
        directory = get_location_directory()
        origin = directory.resolve_one(origin_code)[0]
        destination = directory.resolve_one(destination_code)[0]
        if not origin or not destination:
            await callback.answer("Не удалось распознать маршрут", show_alert=True)
            return
        await state.clear()
        await state.update_data(
            origin_code=origin.code,
            origin_name=origin.name,
            origin_kind=origin.kind,
            origin_search=",".join(origin.search_codes),
            destination_code=destination.code,
            destination_name=destination.name,
            destination_kind=destination.kind,
            destination_search=",".join(destination.search_codes),
        )
        await state.set_state(AddWatch.depart_date)
        await callback.answer()
        await callback.message.answer(
            f"Маршрут <b>{origin.short_label} → {destination.short_label}</b>\n"
            "Введите дату или нажмите «Любая дата».",
            parse_mode="HTML",
            reply_markup=kb.skip_date_kb(),
        )

    @router.callback_query(F.data.startswith("pick_origin:"))
    async def pick_origin(callback: CallbackQuery, state: FSMContext) -> None:
        code = callback.data.split(":")[1]
        await get_location_directory().ensure_loaded()
        place = get_location_directory().resolve_one(code)[0]
        if not place:
            await callback.answer("Не найдено", show_alert=True)
            return
        await callback.answer()
        await _set_origin_and_ask_dest(callback.message, state, place)

    @router.callback_query(F.data.startswith("pick_dest:"))
    async def pick_dest(callback: CallbackQuery, state: FSMContext) -> None:
        code = callback.data.split(":")[1]
        await get_location_directory().ensure_loaded()
        place = get_location_directory().resolve_one(code)[0]
        if not place:
            await callback.answer("Не найдено", show_alert=True)
            return
        await callback.answer()
        await _set_dest_and_ask_date(callback.message, state, place)

    @router.message(AddWatch.origin)
    async def add_origin(message: Message, state: FSMContext) -> None:
        place, candidates = await resolve_place(message.text or "")
        if place:
            await _set_origin_and_ask_dest(message, state, place)
            return
        if candidates:
            await _ask_place_choice(
                message, candidates, prefix="pick_origin", title="Нашёл несколько вариантов вылета."
            )
            return
        await message.answer(
            "Не распознал город. Попробуйте <code>Москва</code>, <code>СПб</code> или код <code>MOW</code>.",
            parse_mode="HTML",
        )

    @router.message(AddWatch.destination)
    async def add_destination(message: Message, state: FSMContext) -> None:
        place, candidates = await resolve_place(message.text or "")
        if place:
            await _set_dest_and_ask_date(message, state, place)
            return
        if candidates:
            await _ask_place_choice(
                message, candidates, prefix="pick_dest", title="Нашёл несколько вариантов прилёта."
            )
            return
        await message.answer(
            "Не распознал город. Попробуйте <code>Анталья</code> или код <code>AYT</code>.",
            parse_mode="HTML",
        )

    @router.message(AddWatch.depart_date, F.text == "📅 Любая дата")
    async def add_any_date(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        origin = _place_from_data("origin", data)
        destination = _place_from_data("destination", data)
        if not origin or not destination:
            await message.answer("Сессия истекла. Нажмите ➕ Добавить", reply_markup=menu())
            await state.clear()
            return
        await _show_route_preview(message, settings, provider, state, origin, destination, None)

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
        origin = _place_from_data("origin", data)
        destination = _place_from_data("destination", data)
        if not origin or not destination:
            await message.answer("Сессия истекла. Нажмите ➕ Добавить", reply_markup=menu())
            await state.clear()
            return
        await _show_route_preview(message, settings, provider, state, origin, destination, depart_date)

    @router.callback_query(F.data.startswith("thr:"))
    async def choose_threshold(callback: CallbackQuery, state: FSMContext) -> None:
        parts = callback.data.split(":")
        if len(parts) < 4:
            await callback.answer("Ошибка кнопки", show_alert=True)
            return
        _, _draft_id, kind, price_raw = parts
        data = await state.get_data()
        if not data.get("origin_code"):
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
        watch_id = await _create_watch_from_state(
            telegram_id=callback.from_user.id,
            username=callback.from_user.username,
            settings=settings,
            data=data,
            max_price=max_price,
        )
        await state.clear()
        await callback.answer("Готово")
        await _confirm_watch_message(callback.message, settings, provider, data, watch_id, max_price)

    @router.message(AddWatch.custom_price)
    async def add_custom_price(message: Message, state: FSMContext) -> None:
        max_price = _parse_price(message.text or "")
        if max_price is None:
            await message.answer("Введите число, например 12000.")
            return
        data = await state.get_data()
        if not data.get("origin_code"):
            await state.clear()
            await message.answer("Сессия истекла. Нажмите ➕ Добавить", reply_markup=menu())
            return
        watch_id = await _create_watch_from_state(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            settings=settings,
            data=data,
            max_price=max_price,
        )
        await state.clear()
        await _confirm_watch_message(message, settings, provider, data, watch_id, max_price)

    @router.message(Command("watch"))
    async def cmd_watch(message: Message, command: CommandObject, state: FSMContext) -> None:
        args = (command.args or "").strip()
        if not args:
            await start_add(message, state)
            return

        await get_location_directory().ensure_loaded()
        # Поддержка: /watch Москва Анталья 12000 [дата]
        # и /watch MOW AYT 12000 [дата]
        tokens = args.split()
        # Собираем origin/dest: если первый токен IATA — два IATA, иначе два слова-города
        origin_text: str
        dest_text: str
        rest: list[str]
        if len(tokens) >= 2 and re.fullmatch(r"[A-Za-z]{3}", tokens[0]) and re.fullmatch(r"[A-Za-z]{3}", tokens[1]):
            origin_text, dest_text, rest = tokens[0], tokens[1], tokens[2:]
        elif len(tokens) >= 2:
            origin_text, dest_text, rest = tokens[0], tokens[1], tokens[2:]
        else:
            await start_add(message, state)
            return

        origin, origin_cands = await resolve_place(origin_text)
        destination, dest_cands = await resolve_place(dest_text)
        if not origin:
            if origin_cands:
                await state.set_state(AddWatch.origin)
                await _ask_place_choice(
                    message, origin_cands, prefix="pick_origin", title="Уточните город вылета."
                )
                return
            await message.answer(f"Не распознал откуда: <b>{origin_text}</b>", parse_mode="HTML")
            return
        if not destination:
            if dest_cands:
                await state.update_data(
                    origin_code=origin.code,
                    origin_name=origin.name,
                    origin_kind=origin.kind,
                    origin_search=",".join(origin.search_codes),
                )
                await state.set_state(AddWatch.destination)
                await _ask_place_choice(
                    message, dest_cands, prefix="pick_dest", title="Уточните город прилёта."
                )
                return
            await message.answer(f"Не распознал куда: <b>{dest_text}</b>", parse_mode="HTML")
            return

        max_price = None
        depart_date = None
        if rest:
            maybe_price = _parse_price(rest[0])
            maybe_date = _parse_date(rest[0])
            if maybe_date and (maybe_price is None or "." in rest[0] or "-" in rest[0]):
                # ambiguous number dates rare; prefer date if parseable as date with separators
                if "-" in rest[0] or "." in rest[0]:
                    depart_date = maybe_date
                elif maybe_price is not None:
                    max_price = maybe_price
            elif maybe_price is not None:
                max_price = maybe_price
            elif maybe_date is not None:
                depart_date = maybe_date
        if len(rest) >= 2:
            depart_date = _parse_date(rest[1]) or depart_date
            if max_price is None:
                max_price = _parse_price(rest[1])

        data = {
            "origin_code": origin.code,
            "origin_name": origin.name,
            "origin_kind": origin.kind,
            "origin_search": ",".join(origin.search_codes),
            "destination_code": destination.code,
            "destination_name": destination.name,
            "destination_kind": destination.kind,
            "destination_search": ",".join(destination.search_codes),
            "depart_date": depart_date.isoformat() if depart_date else None,
        }
        await state.clear()
        await state.update_data(**data)

        if max_price is not None:
            watch_id = await _create_watch_from_state(
                telegram_id=message.from_user.id,
                username=message.from_user.username,
                settings=settings,
                data=data,
                max_price=max_price,
            )
            await _confirm_watch_message(message, settings, provider, data, watch_id, max_price)
            return

        if depart_date is not None:
            await _show_route_preview(
                message, settings, provider, state, origin, destination, depart_date
            )
        else:
            await state.set_state(AddWatch.depart_date)
            await message.answer(
                f"Маршрут <b>{origin.short_label} → {destination.short_label}</b>\n"
                "Введите дату или нажмите «Любая дата».",
                parse_mode="HTML",
                reply_markup=kb.skip_date_kb(),
            )

    async def _render_watch_card(message: Message, w: Watch, title: str | None = None) -> None:
        quote = None
        band = None
        try:
            quote = await provider.get_cheapest_across(
                w.origin_codes, w.destination_codes, w.depart_date, w.currency.lower()
            )
            band = await provider.get_price_band(
                w.origin, w.destination, w.depart_date, w.currency.lower()
            )
        except Exception:
            pass
        if quote is None and w.last_price is not None:
            quote = PriceQuote(
                price=w.last_price,
                currency=w.currency,
                source="cache",
                origin_code=w.last_origin_airport,
                destination_code=w.last_destination_airport,
            )
        link = build_affiliate_url(w.origin, w.destination, settings.affiliate_marker, w.depart_date)
        text = fmt.format_price_card(
            origin=w.origin,
            destination=w.destination,
            depart_date=w.depart_date,
            quote=quote,
            band=band,
            threshold=w.max_price,
            title=title,
            watch_id=w.id,
            origin_name=w.origin_name,
            destination_name=w.destination_name,
        )
        await message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.watch_actions_kb(w.id, link),
            disable_web_page_preview=True,
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
                "Подписок пока нет.\nДобавьте маршрут городом, например Москва → Анталья.",
                reply_markup=kb.list_empty_kb(),
            )
            return

        await message.answer(
            f"Ваши маршруты: <b>{len(watches)}</b>",
            parse_mode="HTML",
            reply_markup=menu(),
        )
        for w in watches:
            await _render_watch_card(message, w)

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
            reply_markup=menu(),
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
            snapshot = watch

        quote = await provider.get_cheapest_across(
            snapshot.origin_codes,
            snapshot.destination_codes,
            snapshot.depart_date,
            snapshot.currency.lower(),
        )
        if quote is not None:
            async with session_scope() as session:
                fresh = await session.get(Watch, watch_id)
                if fresh:
                    fresh.last_price = quote.price
                    fresh.last_checked_at = datetime.now(timezone.utc)
                    fresh.last_origin_airport = quote.origin_code
                    fresh.last_destination_airport = quote.destination_code

        await _render_watch_card(callback.message, snapshot, title="Актуальная цена")

    @router.message(Command("check"))
    @router.message(F.text == "🔄 Проверить цены")
    async def cmd_check(message: Message) -> None:
        await message.answer("Проверяю все маршруты…", reply_markup=menu())
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
            await _render_watch_card(message, w)

        if alerts:
            await message.answer(f"Алертов отправлено: {alerts}")

    @router.message(StateFilter(None), F.text)
    async def fallback(message: Message) -> None:
        await message.answer(
            "Выберите действие на клавиатуре или нажмите ℹ️ Помощь",
            reply_markup=menu(),
        )

    return router


def create_dispatcher(settings: Settings, bot: Bot) -> tuple[Dispatcher, PriceChecker]:
    provider = build_price_provider(settings)
    checker = PriceChecker(bot=bot, settings=settings, provider=provider)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(create_router(settings, checker, provider))
    return dp, checker
