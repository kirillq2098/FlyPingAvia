from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu(webapp_url: str | None = None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    if webapp_url:
        builder.row(
            KeyboardButton(
                text="🛩 Открыть приложение",
                web_app=WebAppInfo(url=webapp_url),
            )
        )
    builder.row(
        KeyboardButton(text="➕ Добавить"),
        KeyboardButton(text="📋 Мои маршруты"),
    )
    builder.row(
        KeyboardButton(text="🔄 Проверить цены"),
        KeyboardButton(text="ℹ️ Помощь"),
    )
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def skip_date_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 Любая дата"))
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def popular_routes_kb() -> InlineKeyboardMarkup:
    routes = [
        ("MOW", "AYT", "Москва → Анталья"),
        ("MOW", "IST", "Москва → Стамбул"),
        ("MOW", "DXB", "Москва → Дубай"),
        ("LED", "AYT", "СПб → Анталья"),
        ("MOW", "SSH", "Москва → Шарм"),
    ]
    builder = InlineKeyboardBuilder()
    for origin, dest, title in routes:
        builder.row(
            InlineKeyboardButton(
                text=title,
                callback_data=f"quick:{origin}:{dest}",
            )
        )
    return builder.as_markup()


def threshold_kb(
    watch_draft_id: str,
    cheap: int,
    typical: int,
) -> InlineKeyboardMarkup:
    """Кнопки выбора порога по вилке цен."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"🟢 Дёшево ≤ {cheap:,} ₽".replace(",", " "),
            callback_data=f"thr:{watch_draft_id}:cheap:{cheap}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"🟡 Обычно ~ {typical:,} ₽".replace(",", " "),
            callback_data=f"thr:{watch_draft_id}:typical:{typical}",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Своя цена",
            callback_data=f"thr:{watch_draft_id}:custom:0",
        )
    )
    return builder.as_markup()


def watch_actions_kb(watch_id: int, tickets_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔎 Цена сейчас", callback_data=f"wcheck:{watch_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"wdel:{watch_id}"),
    )
    builder.row(InlineKeyboardButton(text="🎫 Смотреть билеты", url=tickets_url))
    return builder.as_markup()


def after_watch_kb(watch_id: int, tickets_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Мои маршруты", callback_data="menu:list"),
        InlineKeyboardButton(text="🔎 Проверить", callback_data=f"wcheck:{watch_id}"),
    )
    builder.row(InlineKeyboardButton(text="🎫 Открыть билеты", url=tickets_url))
    return builder.as_markup()


def open_app_kb(webapp_url: str | None = None) -> InlineKeyboardMarkup | None:
    if not webapp_url:
        return None
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="🛩 Открыть приложение",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    return builder.as_markup()


def places_kb(prefix: str, places: list) -> InlineKeyboardMarkup:
    """prefix: pick_origin | pick_dest"""
    builder = InlineKeyboardBuilder()
    for place in places[:10]:
        builder.row(
            InlineKeyboardButton(
                text=place.short_label[:64],
                callback_data=f"{prefix}:{place.code}",
            )
        )
    return builder.as_markup()


def list_empty_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="➕ Добавить маршрут", callback_data="menu:add"))
    return builder.as_markup()
