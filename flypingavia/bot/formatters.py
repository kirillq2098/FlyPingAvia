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


def format_band_block(band: PriceBand, currency: str = "RUB") -> str:
    return (
        "<b>Вилка по маршруту</b>\n"
        f"🟢 дёшево  ≤ {money(band.cheap_max, currency)}\n"
        f"🟡 обычно  ~ {money(band.typical, currency)}\n"
        f"🔴 дорого  ≥ {money(band.expensive_min, currency)}"
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
    return f"<b>{left} → {right}</b> · {date_part} · {trip}"


def passengers_text(adults: int = 1, children: int = 0, infants: int = 0) -> str:
    parts = [f"взр. {max(1, adults)}"]
    if children:
        parts.append(f"дет. {children}")
    if infants:
        parts.append(f"мл. {infants}")
    return ", ".join(parts)


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
    if title:
        lines.append(f"<b>{title}</b>")
    header = format_route(
        origin,
        destination,
        depart_date,
        origin_name=origin_name,
        destination_name=destination_name,
        return_date=return_date,
    )
    if watch_id is not None:
        header = f"#{watch_id} · {header}"
    lines.append(header)
    lines.append(f"Пассажиры в поиске: {passengers_text(adults, children, infants)}")
    lines.append("")

    if quote is not None:
        level = band.classify(quote.price) if band else PriceLevel.UNKNOWN
        if quote.is_live:
            lines.append(
                f"Сейчас: <b>{money(quote.price, currency)}</b> за всех  ·  {level_label(level)}"
            )
            lines.append("Источник: <b>живой поиск Aviasales</b>")
            if quote.price_per_adult is not None:
                lines.append(f"Ориентир на человека: {money(quote.price_per_adult, currency)}")
        else:
            lines.append(
                f"Сейчас: <b>{money(quote.price, currency)}</b> за 1 взр.  ·  {level_label(level)}"
            )
            if return_date is not None:
                lines.append("Туда+обратно ≈ сумма двух one-way (за 1 взр.)")
            if adults > 1 or children or infants:
                lines.append(
                    "<i>Живой поиск за состав недоступен — показан кэш за 1 взр.</i>"
                )
            else:
                lines.append("<i>Кэш Data API — на сайте сумма может чуть отличаться</i>")
        extras = []
        if quote.transfers is not None:
            extras.append("прямой" if quote.transfers == 0 else f"пересадок: {quote.transfers}")
        if quote.airline:
            extras.append(f"а/к {quote.airline}")
        if extras:
            lines.append(" · ".join(extras))
        if quote.origin_code or quote.destination_code:
            via = []
            if quote.origin_code:
                via.append(f"вылет {quote.origin_code}")
            if quote.destination_code:
                via.append(f"прилёт {quote.destination_code}")
            if quote.return_origin_code:
                via.append(f"обратно из {quote.return_origin_code}")
            lines.append("Самый дешёвый вариант: " + " · ".join(via))
        if len(quote.searched_origins) > 1 or len(quote.searched_destinations) > 1:
            lines.append(
                f"Проверено а/п: {', '.join(quote.searched_origins) or origin}"
                f" → {', '.join(quote.searched_destinations) or destination}"
            )
    else:
        lines.append("Сейчас: цена не найдена")

    if airport_note:
        lines.append(airport_note)

    if band is not None:
        lines.append("")
        lines.append(format_band_block(band, currency))

    if threshold is not None:
        lines.append("")
        lines.append(
            f"Ваш порог ({'за всех' if (quote and quote.is_live) else 'к цене за 1 взр.'}): "
            f"<b>{money(threshold, currency)}</b>"
        )
        if quote is not None:
            if quote.price <= threshold:
                lines.append("✅ уже ниже порога")
            else:
                diff = quote.price - threshold
                lines.append(f"⏳ до порога ещё {money(diff, currency)}")

    return "\n".join(lines)


def welcome_text() -> str:
    return (
        "<b>FlyPingAvia</b>\n"
        "Слежу за ценами на авиабилеты и пишу, когда стало выгодно.\n\n"
        "Можно писать <b>город</b> словами, выбрать <b>пассажиров</b> "
        "(взрослые / дети / младенцы) и билет <b>туда-обратно</b>.\n\n"
        "При живом поиске покажу цену <b>за всех</b>, иначе — кэш за 1 взр."
    )


def help_text() -> str:
    return (
        "<b>Как пользоваться</b>\n\n"
        "1. Нажмите <b>➕ Добавить</b> или откройте приложение\n"
        "2. Укажите города, дату, тип поездки и пассажиров\n"
        "3. Выберите порог по вилке\n\n"
        "Живой поиск (Flight Search API) считает цену за ваш состав. "
        "Если доступа к API ещё нет — бот показывает кэш за 1 взрослого, "
        "а состав всё равно попадает в ссылку на Aviasales.\n\n"
        "Команда:\n"
        "<code>/watch Москва Анталья 25000</code>"
    )
