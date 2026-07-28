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


def format_route(
    origin: str,
    destination: str,
    depart_date: Optional[date] = None,
    *,
    origin_name: Optional[str] = None,
    destination_name: Optional[str] = None,
) -> str:
    if depart_date:
        months = (
            "янв", "фев", "мар", "апр", "мая", "июн",
            "июл", "авг", "сен", "окт", "ноя", "дек",
        )
        date_part = f"{depart_date.day} {months[depart_date.month - 1]} {depart_date.year}"
    else:
        date_part = "любая дата"
    left = f"{origin_name} ({origin})" if origin_name else origin
    right = f"{destination_name} ({destination})" if destination_name else destination
    return f"<b>{left} → {right}</b> · {date_part}"


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
) -> str:
    currency = (quote.currency if quote else None) or (band.currency if band else "RUB")
    lines: list[str] = []
    if title:
        lines.append(f"<b>{title}</b>")
    header = format_route(
        origin,
        destination,
        depart_date,
        origin_name=origin_name,
        destination_name=destination_name,
    )
    if watch_id is not None:
        header = f"#{watch_id} · {header}"
    lines.append(header)
    lines.append("")

    if quote is not None:
        level = band.classify(quote.price) if band else PriceLevel.UNKNOWN
        lines.append(f"Сейчас: <b>{money(quote.price, currency)}</b>  ·  {level_label(level)}")
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
        lines.append(f"Ваш порог: <b>{money(threshold, currency)}</b>")
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
        "Можно писать <b>город</b> словами — аэропорт подставлю сам. "
        "Если в городе несколько аэропортов, проверю все и возьму <b>самый дешёвый</b>.\n\n"
        "Покажу вилку: что дёшево, обычно и дорого — и помогу поставить порог.\n\n"
        "Можно пользоваться чатом или кнопкой <b>Открыть приложение</b> (Mini App)."
    )


def help_text() -> str:
    return (
        "<b>Как пользоваться</b>\n\n"
        "1. Нажмите <b>🛩 Открыть приложение</b> или <b>➕ Добавить</b>\n"
        "2. Напишите город или код: <code>Москва</code>, <code>MOW</code>, <code>Шереметьево</code>\n"
        "3. Укажите дату (или «любая дата»)\n"
        "4. Выберите порог по вилке\n\n"
        "Если аэропортов несколько — ищу по всем, в подписке остаётся самый выгодный вариант.\n\n"
        "Mini App работает внутри Telegram (нужен HTTPS URL в WEBAPP_URL).\n\n"
        "Команда:\n"
        "<code>/watch Москва Анталья 12000</code>\n"
        "<code>/watch MOW AYT 12000 2026-09-10</code>"
    )
