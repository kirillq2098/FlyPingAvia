from __future__ import annotations

from datetime import date
from typing import Optional

from flypingavia.services.prices import PriceBand, PriceLevel, PriceQuote


def money(value: float | int, currency: str = "RUB") -> str:
    amount = f"{int(round(value)):,}".replace(",", " ")
    symbol = "₽" if currency.upper() in {"RUB", "RUR"} else currency.upper()
    return f"{amount} {symbol}"


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
) -> str:
    currency = (quote.currency if quote else None) or (band.currency if band else "RUB")
    if quote is not None:
        adults = quote.adults
        children = quote.children
        infants = quote.infants
        return_date = quote.return_date if quote.return_date is not None else return_date

    lines: list[str] = []

    # 1) Заголовок
    if title:
        lines.append(f"<b>{title}</b>")
    if watch_id is not None:
        lines.append(f"Подписка <code>#{watch_id}</code>")

    # 2) Маршрут
    lines.append("")
    route = format_route(
        origin,
        destination,
        depart_date,
        origin_name=origin_name,
        destination_name=destination_name,
        return_date=return_date,
    )
    lines.append(f"<b>{route.splitlines()[0]}</b>")
    for extra in route.splitlines()[1:]:
        lines.append(extra)
    if adults > 1 or children or infants:
        lines.append(f"Пассажиры: {passengers_text(adults, children, infants)}")

    # 3) Цена — главный акцент
    lines.append("")
    if quote is not None:
        level = band.classify(quote.price) if band else PriceLevel.UNKNOWN
        lines.append(f"<b>{money(quote.price, currency)}</b>")
        if band is not None and level != PriceLevel.UNKNOWN:
            lines.append(f"Относительно рынка: {level_label(level)}")
        meta = _meta_line(quote)
        if meta:
            lines.append(meta)
        if return_date is not None and not quote.is_live:
            lines.append("Туда+обратно ≈ сумма двух one-way")
    else:
        lines.append("<b>Цена не найдена</b>")
        lines.append("Попробуйте другую дату или проверьте позже")

    if airport_note:
        lines.append(airport_note)

    # 4) Вилка рынка
    if band is not None:
        lines.append("")
        lines.append(format_band_block(band, currency))

    # 5) Порог пользователя — отдельно от «рынка»
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

    return "\n".join(lines).strip()


def welcome_text() -> str:
    return (
        "<b>FlyPingAvia</b>\n"
        "Слежу за ценами на авиабилеты и пишу, когда стало выгодно.\n\n"
        "<b>Как начать</b>\n"
        "1. ➕ Добавить — города, дата, тип поездки\n"
        "2. Выберите порог по вилке рынка\n"
        "3. Ждите алерт или откройте Mini App\n\n"
        "Пишите города словами: <code>Москва</code>, <code>Сургут</code>"
    )


def help_text() -> str:
    return (
        "<b>Помощь</b>\n\n"
        "<b>Добавить маршрут</b>\n"
        "Кнопка ➕ или команда:\n"
        "<code>/watch Москва Анталья 25000</code>\n\n"
        "<b>Вилка рынка</b>\n"
        "🟢 дёшево · 🟡 обычно · 🔴 дорого — оценка относительно других дат/предложений.\n"
        "Порог — ваша личная планка: алерт придёт, когда цена ≤ порога.\n\n"
        "<b>Команды</b>\n"
        "/list — подписки\n"
        "/check — проверить сейчас\n"
        "/unwatch ID — удалить"
    )
