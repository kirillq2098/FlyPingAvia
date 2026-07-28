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


def format_route(origin: str, destination: str, depart_date: Optional[date] = None) -> str:
    if depart_date:
        months = (
            "янв", "фев", "мар", "апр", "мая", "июн",
            "июл", "авг", "сен", "окт", "ноя", "дек",
        )
        date_part = f"{depart_date.day} {months[depart_date.month - 1]} {depart_date.year}"
    else:
        date_part = "любая дата"
    return f"<b>{origin} → {destination}</b> · {date_part}"


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
) -> str:
    currency = (quote.currency if quote else None) or (band.currency if band else "RUB")
    lines: list[str] = []
    if title:
        lines.append(f"<b>{title}</b>")
    header = format_route(origin, destination, depart_date)
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
    else:
        lines.append("Сейчас: цена не найдена")

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
        "Покажу вилку: что <b>дёшево</b>, что <b>обычно</b> и что <b>дорого</b> "
        "на вашем маршруте — и помогу поставить понятный порог.\n\n"
        "Выберите действие на клавиатуре ниже."
    )


def help_text() -> str:
    return (
        "<b>Как пользоваться</b>\n\n"
        "1. Нажмите <b>➕ Добавить</b> или быстрый маршрут\n"
        "2. Укажите дату (или «любая дата»)\n"
        "3. Выберите порог по вилке: дёшево / обычно / своя цена\n"
        "4. Бот напишет, когда цена упадёт до порога\n\n"
        "Также можно командой:\n"
        "<code>/watch MOW AYT 12000 2026-09-10</code>\n\n"
        "<b>Кнопки</b>\n"
        "📋 Мои маршруты — список и действия\n"
        "🔄 Проверить цены — обновить сейчас\n"
        "ℹ️ Помощь — эта справка"
    )
