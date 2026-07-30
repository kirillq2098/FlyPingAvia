from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from flypingavia.services.prices import PriceBand, PriceLevel, PriceQuote

DEFAULT_DISPLAY_TZ = ZoneInfo("Europe/Moscow")
_FUTURE_SKEW = timedelta(minutes=2)
_MONTHS_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def money(value: float | int, currency: str = "RUB") -> str:
    amount = f"{int(round(value)):,}".replace(",", " ")
    symbol = "₽" if currency.upper() in {"RUB", "RUR"} else currency.upper()
    return f"{amount} {symbol}"


def _resolve_display_tz(tz: ZoneInfo | str | None) -> ZoneInfo:
    if tz is None:
        return DEFAULT_DISPLAY_TZ
    if isinstance(tz, ZoneInfo):
        return tz
    try:
        return ZoneInfo(str(tz))
    except Exception:
        return DEFAULT_DISPLAY_TZ


def _ensure_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _minutes_word(n: int) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return "минут"
    if n1 == 1:
        return "минуту"
    if 2 <= n1 <= 4:
        return "минуты"
    return "минут"


def _hours_word(n: int) -> str:
    n_abs = abs(n) % 100
    n1 = n_abs % 10
    if 11 <= n_abs <= 14:
        return "часов"
    if n1 == 1:
        return "час"
    if 2 <= n1 <= 4:
        return "часа"
    return "часов"


def format_last_checked(
    value: datetime | None,
    *,
    now: datetime | None = None,
    tz: ZoneInfo | str | None = None,
) -> str:
    """Человекочитаемое время последней проверки (TR-04).

    БД хранит UTC; показ — в бизнес-таймзоне (по умолчанию Europe/Moscow).
    """
    if value is None:
        return "Ещё не проверяли"

    display_tz = _resolve_display_tz(tz)
    now_utc = _ensure_aware_utc(now or datetime.now(timezone.utc))
    try:
        checked_utc = _ensure_aware_utc(value)
    except Exception:
        return "Ещё не проверяли"

    # Небольшой clock skew вперёд → «только что»; далеко в будущем → абсолютное.
    if checked_utc > now_utc + _FUTURE_SKEW:
        local = checked_utc.astimezone(display_tz)
        month = _MONTHS_GENITIVE[local.month - 1]
        return f"Проверено {local.day} {month} в {local.strftime('%H:%M')}"

    if checked_utc > now_utc:
        checked_utc = now_utc

    delta = now_utc - checked_utc
    secs = delta.total_seconds()

    if secs < 60:
        return "Проверено только что"
    if secs < 3600:
        minutes = max(1, int(secs // 60))
        return f"Проверено {minutes} {_minutes_word(minutes)} назад"

    local_checked = checked_utc.astimezone(display_tz)
    local_now = now_utc.astimezone(display_tz)
    checked_day = local_checked.date()
    today = local_now.date()
    yesterday = today - timedelta(days=1)
    time_s = local_checked.strftime("%H:%M")

    if secs < 12 * 3600 and checked_day == today:
        hours = max(1, int(secs // 3600))
        return f"Проверено {hours} {_hours_word(hours)} назад"
    if checked_day == today:
        return f"Проверено сегодня в {time_s}"
    if checked_day == yesterday:
        return f"Проверено вчера в {time_s}"

    month = _MONTHS_GENITIVE[local_checked.month - 1]
    return f"Проверено {local_checked.day} {month} в {time_s}"


def format_last_checked_line(
    value: datetime | None,
    *,
    now: datetime | None = None,
    tz: ZoneInfo | str | None = None,
    alert: bool = False,
) -> str:
    """Строка для Telegram-карточки / алерта с эмодзи."""
    text = format_last_checked(value, now=now, tz=tz)
    if text == "Ещё не проверяли":
        return f"🕒 {text}"
    if alert:
        rest = text.removeprefix("Проверено").strip()
        return f"🕒 Проверено: {rest}"
    return f"🕒 {text}"


def level_label(level: PriceLevel) -> str:
    return {
        PriceLevel.CHEAP: "🟢 дёшево",
        PriceLevel.NORMAL: "🟡 обычно",
        PriceLevel.EXPENSIVE: "🔴 дорого",
        PriceLevel.UNKNOWN: "⚪ нет оценки",
    }[level]


def level_short(level: PriceLevel) -> str:
    return {
        PriceLevel.CHEAP: "дёшево",
        PriceLevel.NORMAL: "обычно",
        PriceLevel.EXPENSIVE: "дорого",
        PriceLevel.UNKNOWN: "нет оценки",
    }[level]


def format_band_block(band: PriceBand, currency: str = "RUB") -> str:
    return (
        "<b>Рынок по маршруту</b>\n"
        f"🟢 дёшево  ≤ {money(band.cheap_max, currency)}\n"
        f"🟡 обычно   ~ {money(band.typical, currency)}\n"
        f"🔴 дорого   ≥ {money(band.expensive_min, currency)}"
    )


def format_market_assessment(
    price: float,
    band: Optional[PriceBand],
    currency: str = "RUB",
    *,
    round_trip: bool = False,
) -> Optional[str]:
    """NT-03: компактная оценка найденной цены относительно рынка.

    Возвращает None, если данных недостаточно — алерт должен работать без блока.
    Не использует порог пользователя и не выдаёт ориентир за гарантированную цену.
    """
    if band is None:
        return None
    if band.sample_size < 1:
        return None
    if band.typical <= 0 or band.cheap_max <= 0 or band.expensive_min <= 0:
        return None

    level = band.classify(price)
    if level == PriceLevel.UNKNOWN:
        return None

    headline = {
        PriceLevel.CHEAP: "🟢 Дёшево относительно рынка",
        PriceLevel.NORMAL: "🟡 Обычная цена",
        PriceLevel.EXPENSIVE: "🔴 Дороже обычного",
    }[level]

    # RT band ≈ ×2 one-way — нейтральная формулировка, без ложной точности.
    if round_trip:
        orient = f"Ориентир по текущим данным: около {money(band.typical, currency)}"
    elif level == PriceLevel.CHEAP:
        orient = f"Обычно по этому направлению: около {money(band.typical, currency)}"
    else:
        orient = f"Рыночный ориентир: около {money(band.typical, currency)}"

    return f"{headline}\n{orient}"


def _fmt_day(value: Optional[date]) -> str:
    if not value:
        return "любая дата"
    months = (
        "янв", "фев", "мар", "апр", "мая", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек",
    )
    return f"{value.day} {months[value.month - 1]} {value.year}"


def format_route(
    origin: str,
    destination: str,
    depart_date: Optional[date] = None,
    *,
    origin_name: Optional[str] = None,
    destination_name: Optional[str] = None,
    return_date: Optional[date] = None,
) -> str:
    left = f"{origin_name} ({origin})" if origin_name else origin
    right = f"{destination_name} ({destination})" if destination_name else destination
    if return_date is not None:
        date_part = f"{_fmt_day(depart_date)} ⇄ {_fmt_day(return_date)}"
        trip = "туда-обратно"
    else:
        date_part = _fmt_day(depart_date)
        trip = "в одну сторону"
    return f"{left} → {right}\n{date_part} · {trip}"


def passengers_text(adults: int = 1, children: int = 0, infants: int = 0) -> str:
    parts = [f"взр. {max(1, adults)}"]
    if children:
        parts.append(f"дет. {children}")
    if infants:
        parts.append(f"мл. {infants}")
    return ", ".join(parts)


def _meta_line(quote: PriceQuote) -> Optional[str]:
    parts: list[str] = []
    if quote.transfers is not None:
        parts.append("прямой" if quote.transfers == 0 else f"пересадок: {quote.transfers}")
    if quote.airline:
        parts.append(quote.airline)
    airports: list[str] = []
    if quote.origin_code:
        airports.append(quote.origin_code)
    if quote.destination_code:
        airports.append(quote.destination_code)
    if airports:
        parts.append("→".join(airports))
    if quote.return_origin_code:
        parts.append(f"обратно из {quote.return_origin_code}")
    return " · ".join(parts) if parts else None


def format_threshold_contract(
    price: float,
    threshold: float,
    currency: str = "RUB",
) -> str:
    """NT-02: явный контракт X ≤ Y и дельта к пользовательскому порогу.

    Дельта — только Y − X (разница до порога), не рыночная/историческая экономия.
    """
    x = money(price, currency)
    y = money(threshold, currency)
    lines = [
        f"Текущая цена: {x}",
        f"Ваш порог: {y}",
    ]
    if price <= threshold:
        delta = threshold - price
        lines.append(f"✅ {x} ≤ {y}")
        lines.append(f"Выгода к порогу: {money(delta, currency)}")
    else:
        diff = price - threshold
        lines.append(f"⏳ до порога ещё {money(diff, currency)}")
    return "\n".join(lines)


def format_low_threshold_warning(
    threshold: float,
    cheap_max: float,
    currency: str = "RUB",
) -> str:
    """CS-05: спокойное предупреждение о пороге ниже дешёвой зоны рынка."""
    return (
        "⚠️ <b>Порог заметно ниже текущего рынка</b>\n\n"
        f"Вы выбрали: {money(threshold, currency)}\n"
        f"Дешёвая цена по текущим данным: до {money(cheap_max, currency)}\n\n"
        "С таким порогом уведомление может долго не прийти.\n"
        "Можно сохранить этот порог или вернуться и изменить его."
    )


def _days_word(n: int) -> str:
    n_abs = abs(int(n))
    mod10 = n_abs % 10
    mod100 = n_abs % 100
    if mod10 == 1 and mod100 != 11:
        return "день"
    if 2 <= mod10 <= 4 and not (12 <= mod100 <= 14):
        return "дня"
    return "дней"


def format_offset_label(offset_days: int) -> str:
    """Единый формат сдвига: +2 дня / −2 дня."""
    sign = "−" if offset_days < 0 else "+"
    n = abs(int(offset_days))
    return f"{sign}{n} {_days_word(n)}"


def format_flexible_offset_block(
    *,
    found_depart: date,
    found_return: date | None,
    primary_depart: date,
    primary_return: date | None,
    offset_days: int,
) -> str | None:
    """CS-07: блок соседней даты в алерте; None при offset=0."""
    if offset_days == 0:
        return None
    shift = format_offset_label(offset_days)
    if found_return is not None and primary_return is not None:
        return (
            f"📅 Цена найдена на соседнюю дату: {_fmt_day(found_depart)} – {_fmt_day(found_return)}\n"
            f"Основные даты: {_fmt_day(primary_depart)} – {_fmt_day(primary_return)} · сдвиг {shift}"
        )
    return (
        f"📅 Цена найдена на соседнюю дату: {_fmt_day(found_depart)}\n"
        f"Основная дата: {_fmt_day(primary_depart)} · сдвиг {shift}"
    )


def format_flexibility_summary(
    *,
    depart_date: Optional[date],
    return_date: Optional[date] = None,
    flexibility_days: int = 0,
) -> str:
    """Краткое описание гибкости для карточек Watch / подтверждения."""
    flex = max(0, int(flexibility_days or 0))
    if not depart_date:
        return "Дата: любая"
    if return_date is not None:
        base = f"Основные даты: {_fmt_day(depart_date)} – {_fmt_day(return_date)}"
        if flex == 0:
            return base
        trip_len = (return_date - depart_date).days
        return (
            f"{base}\n"
            f"Гибкость: ±{flex} {_days_word(flex)}, длительность поездки сохраняется "
            f"({trip_len} {_days_word(trip_len)})"
        )
    if flex == 0:
        return f"Дата: {_fmt_day(depart_date)}"
    window_from = depart_date - timedelta(days=flex)
    window_to = depart_date + timedelta(days=flex)
    return (
        f"Основная дата: {_fmt_day(depart_date)}\n"
        f"Гибкость: ±{flex} {_days_word(flex)} ({_fmt_day(window_from)} – {_fmt_day(window_to)})"
    )


def format_price_card(
    *,
    origin: str,
    destination: str,
    depart_date: Optional[date],
    quote: Optional[PriceQuote],
    band: Optional[PriceBand],
    threshold: Optional[float] = None,
    title: str | None = None,
    watch_id: int | None = None,
    origin_name: Optional[str] = None,
    destination_name: Optional[str] = None,
    airport_note: Optional[str] = None,
    return_date: Optional[date] = None,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    threshold_contract: bool = False,
    found_depart_date: Optional[date] = None,
    found_return_date: Optional[date] = None,
    offset_days: int = 0,
    primary_depart_date: Optional[date] = None,
    primary_return_date: Optional[date] = None,
    flexibility_days: int = 0,
    checked_at: datetime | None = None,
    show_checked_at: bool | None = None,
    display_timezone: ZoneInfo | str | None = None,
    now: datetime | None = None,
) -> str:
    currency = (quote.currency if quote else None) or (band.currency if band else "RUB")
    if quote is not None:
        adults = quote.adults
        children = quote.children
        infants = quote.infants
        return_date = quote.return_date if quote.return_date is not None else return_date

    display_depart = found_depart_date if found_depart_date is not None else depart_date
    display_return = found_return_date if found_return_date is not None else return_date
    primary_dep = primary_depart_date if primary_depart_date is not None else depart_date
    primary_ret = primary_return_date if primary_return_date is not None else return_date

    lines: list[str] = []

    # 1) Заголовок
    if title:
        lines.append(f"<b>{title}</b>")
    if watch_id is not None:
        lines.append(f"Подписка <code>#{watch_id}</code>")

    # 2) Маршрут (для алерта — фактические найденные даты)
    lines.append("")
    route = format_route(
        origin,
        destination,
        display_depart,
        origin_name=origin_name,
        destination_name=destination_name,
        return_date=display_return,
    )
    lines.append(f"<b>{route.splitlines()[0]}</b>")
    for extra in route.splitlines()[1:]:
        lines.append(extra)
    if adults > 1 or children or infants:
        lines.append(f"Пассажиры: {passengers_text(adults, children, infants)}")
    if flexibility_days and not threshold_contract:
        lines.append(
            format_flexibility_summary(
                depart_date=primary_dep or depart_date,
                return_date=primary_ret if primary_ret is not None else return_date,
                flexibility_days=flexibility_days,
            )
        )

    # CS-07: соседняя дата в алерте
    if threshold_contract and offset_days and found_depart_date is not None and primary_dep is not None:
        flex_block = format_flexible_offset_block(
            found_depart=found_depart_date,
            found_return=found_return_date,
            primary_depart=primary_dep,
            primary_return=primary_ret,
            offset_days=offset_days,
        )
        if flex_block:
            lines.append("")
            lines.append(flex_block)

    # 3) Цена — главный акцент
    lines.append("")
    if quote is not None:
        level = band.classify(quote.price) if band else PriceLevel.UNKNOWN
        lines.append(f"<b>{money(quote.price, currency)}</b>")
        # В алерте (threshold_contract) рынок идёт отдельным блоком после порога (NT-03).
        if not threshold_contract and band is not None and level != PriceLevel.UNKNOWN:
            lines.append(f"Относительно рынка: {level_label(level)}")
        meta = _meta_line(quote)
        if meta:
            lines.append(meta)
        if display_return is not None and not quote.is_live:
            lines.append("Туда+обратно ≈ сумма двух one-way")
    else:
        lines.append("<b>Цена не найдена</b>")
        lines.append("Попробуйте другую дату или проверьте позже")

    if airport_note:
        lines.append(airport_note)

    is_round_trip = display_return is not None or (
        quote is not None and quote.return_date is not None
    )

    if threshold_contract:
        # Алерт: NT-02 контракт → NT-03 рыночная оценка (без полной вилки-таблицы).
        if threshold is not None and quote is not None:
            lines.append("")
            lines.append(format_threshold_contract(quote.price, threshold, currency))
        elif threshold is not None:
            lines.append("")
            lines.append(f"<b>Ваш порог</b> · {money(threshold, currency)}")

        if quote is not None:
            assessment = format_market_assessment(
                quote.price,
                band,
                currency,
                round_trip=is_round_trip,
            )
            if assessment:
                lines.append("")
                lines.append(assessment)
    else:
        # Обычные карточки: полная вилка, затем краткий статус порога.
        if band is not None:
            lines.append("")
            lines.append(format_band_block(band, currency))

        if threshold is not None:
            lines.append("")
            lines.append(f"<b>Ваш порог</b> · {money(threshold, currency)}")
            if quote is not None:
                if quote.price <= threshold:
                    saved = threshold - quote.price
                    lines.append(f"✅ ниже порога на {money(saved, currency)}")
                else:
                    diff = quote.price - threshold
                    lines.append(f"⏳ до порога ещё {money(diff, currency)}")

    # TR-04: время проверки — после цены / NT-02 / NT-03.
    include_checked = (
        show_checked_at
        if show_checked_at is not None
        else (watch_id is not None or threshold_contract or checked_at is not None)
    )
    if include_checked:
        lines.append("")
        lines.append(
            format_last_checked_line(
                checked_at,
                now=now,
                tz=display_timezone,
                alert=threshold_contract,
            )
        )

    return "\n".join(lines).strip()


def welcome_text() -> str:
    return (
        "<b>FlyPingAvia</b> — мониторинг цен на авиабилеты\n\n"
        "Вы задаёте маршрут и максимальную цену.\n"
        "Я проверяю предложения и пишу, когда билет стал ≤ вашего порога.\n\n"
        "<b>Что умею</b>\n"
        "• города словами — <code>Москва</code>, <code>Сургут</code>\n"
        "• билет в одну сторону или туда-обратно\n"
        "• вилка рынка: 🟢 дёшево · 🟡 обычно · 🔴 дорого\n"
        "• алерты и партнёрские ссылки на билеты\n\n"
        "<b>Как начать</b>\n"
        "1. Нажмите <b>➕ Добавить</b>\n"
        "2. Укажите откуда / куда / дату\n"
        "3. Выберите порог по вилке или введите свой\n\n"
        "Дальше можно ничего не делать — напишу сам, когда цена станет выгодной."
    )


def mini_app_text(host: str) -> str:
    _ = host
    return (
        "<b>Mini App</b> — то же самое в удобном окне внутри Telegram.\n\n"
        "Нажмите кнопку ниже: поиск, вилка цен и подписки в одном экране."
    )


def help_text() -> str:
    return (
        "<b>Помощь</b>\n\n"
        "<b>Добавить маршрут</b>\n"
        "Кнопка <b>➕ Добавить</b> или команда:\n"
        "<code>/watch Москва Анталья 25000</code>\n\n"
        "<b>Рынок и порог</b>\n"
        "🟢 / 🟡 / 🔴 — насколько цена хороша относительно рынка.\n"
        "Порог — ваша планка: алерт приходит, когда цена ≤ порога.\n\n"
        "<b>Команды</b>\n"
        "/list — мои подписки\n"
        "/check — проверить цены сейчас\n"
        "/unwatch ID — удалить подписку\n"
        "/help — эта справка"
    )
