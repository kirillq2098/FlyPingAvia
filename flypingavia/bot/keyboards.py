from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# TG-02: пользовательские подписи кнопок (callback data не меняем)
BTN_OPEN_FLYPING = "🌐 Открыть FlyPing"
BTN_CREATE_WATCH = "➕ Создать подписку"
BTN_MY_WATCHES = "📋 Мои подписки"
BTN_CHECK_PRICES = "🔄 Проверить цены"
BTN_HELP = "ℹ️ Помощь"


def main_menu(webapp_url: str | None = None) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    # Только canonical публичный HTTPS — не localhost и не пустой URL.
    if webapp_url:
        builder.row(
            KeyboardButton(
                text=BTN_OPEN_FLYPING,
                web_app=WebAppInfo(url=webapp_url),
            )
        )
    builder.row(
        KeyboardButton(text=BTN_CREATE_WATCH),
        KeyboardButton(text=BTN_MY_WATCHES),
    )
    builder.row(
        KeyboardButton(text=BTN_CHECK_PRICES),
        KeyboardButton(text=BTN_HELP),
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


def low_threshold_confirm_kb() -> InlineKeyboardMarkup:
    """CS-05: подтверждение сохранения низкого порога."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Сохранить этот порог",
            callback_data="lowthr:save",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Изменить порог",
            callback_data="lowthr:edit",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="📊 Варианты по рынку",
            callback_data="lowthr:presets",
        )
    )
    return builder.as_markup()


def watch_actions_kb(watch_id: int, tickets_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔎 Цена сейчас", callback_data=f"wcheck:{watch_id}"),
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"wdel:{watch_id}"),
    )
    builder.row(
        InlineKeyboardButton(text="🔗 Поделиться", callback_data=f"wshare:{watch_id}"),
        InlineKeyboardButton(text="🔒 Отозвать ссылки", callback_data=f"wshare_revoke:{watch_id}"),
    )
    builder.row(InlineKeyboardButton(text="🎫 Смотреть билеты", url=tickets_url))
    return builder.as_markup()


def share_confirm_kb(callback_proof: str) -> InlineKeyboardMarkup:
    """Confirm с HMAC proof (не сырой share_id)."""
    if len(callback_proof.encode("utf-8")) > 64:
        raise ValueError("callback_data превышает лимит Telegram (64 bytes)")
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Создать подписку",
            callback_data=callback_proof,
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="❌ Не нужно",
            callback_data="share_cancel",
        )
    )
    return builder.as_markup()


def share_link_kb(share_url: str, share_text: str = "Следи за ценой на эту поездку в FlyPing") -> InlineKeyboardMarkup:
    from urllib.parse import urlencode

    share_page = "https://t.me/share/url?" + urlencode({"url": share_url, "text": share_text})
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📤 Отправить ссылку", url=share_page)
    )
    return builder.as_markup()


def after_watch_kb(watch_id: int, tickets_url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Мои подписки", callback_data="menu:list"),
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
            text="🌐 Открыть FlyPing",
            web_app=WebAppInfo(url=webapp_url),
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="Открыть в браузере",
            url=webapp_url,
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


def trip_type_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➡ В одну сторону", callback_data="trip:oneway"),
    )
    builder.row(
        InlineKeyboardButton(text="🔁 Туда и обратно", callback_data="trip:round"),
    )
    return builder.as_markup()


def flexibility_kb() -> InlineKeyboardMarkup:
    """CS-07 MVP: окно дат вокруг основной даты."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎯 Только эта дата", callback_data="flex:0"),
    )
    builder.row(
        InlineKeyboardButton(text="±1 день", callback_data="flex:1"),
        InlineKeyboardButton(text="±3 дня", callback_data="flex:3"),
    )
    builder.row(
        InlineKeyboardButton(text="±7 дней", callback_data="flex:7"),
    )
    return builder.as_markup()


def skip_return_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="📅 Обратно +7 дней"))
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup()


def passengers_kb(adults: int, children: int, infants: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➖", callback_data="pax:adults:-"),
        InlineKeyboardButton(text=f"Взрослые: {adults}", callback_data="pax:noop"),
        InlineKeyboardButton(text="➕", callback_data="pax:adults:+"),
    )
    builder.row(
        InlineKeyboardButton(text="➖", callback_data="pax:children:-"),
        InlineKeyboardButton(text=f"Дети 2–12: {children}", callback_data="pax:noop"),
        InlineKeyboardButton(text="➕", callback_data="pax:children:+"),
    )
    builder.row(
        InlineKeyboardButton(text="➖", callback_data="pax:infants:-"),
        InlineKeyboardButton(text=f"Младенцы 0–2: {infants}", callback_data="pax:noop"),
        InlineKeyboardButton(text="➕", callback_data="pax:infants:+"),
    )
    builder.row(InlineKeyboardButton(text="✅ Далее", callback_data="pax:done"))
    return builder.as_markup()


def list_empty_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="➕ Создать подписку", callback_data="menu:add")
    )
    return builder.as_markup()
