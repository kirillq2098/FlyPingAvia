"""Telegram closed admin dashboard: /admin + callbacks (read-only)."""

from __future__ import annotations

import logging
from datetime import date, datetime
from html import escape
from typing import Optional
from zoneinfo import ZoneInfo

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from flypingavia.bot.formatters import money
from flypingavia.config import Settings
from flypingavia.db.session import session_scope
from flypingavia.services import admin_stats as stats
from flypingavia.version import get_version

logger = logging.getLogger(__name__)

# Short callback namespace (Telegram limit 64 bytes).
CB_MAIN = "ad:m"
CB_USERS = "ad:u"
CB_USER = "ad:ud"
CB_WATCHES = "ad:w"
CB_FUNNEL = "ad:f"
CB_SOURCES = "ad:s"
CB_ALERTS = "ad:a"
CB_SYSTEM = "ad:sys"
CB_BUGS = "ad:b"


def _is_admin_user(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.admin_user_id_set


def _display_name(username: str | None, *, fallback: str = "без username") -> str:
    if username and str(username).strip():
        return f"@{escape(str(username).strip())}"
    return escape(fallback)


def _fmt_dt(value: datetime | None, tz: ZoneInfo) -> str:
    if value is None:
        return "—"
    dt = value if value.tzinfo else value.replace(tzinfo=ZoneInfo("UTC"))
    local = dt.astimezone(tz)
    return f"{local.day:02d}.{local.month:02d} {local.hour:02d}:{local.minute:02d}"


def _fmt_date(value: date | None) -> str:
    if value is None:
        return "любая"
    return f"{value.day:02d}.{value.month:02d}"


def _pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "—"
    return f"{round(100.0 * part / whole)}%"


def _status_icon(ok: bool | None) -> str:
    if ok is True:
        return "✅"
    if ok is False:
        return "❌"
    return "⚪"


def _nav_row(*, back: str | None, refresh: str) -> list[InlineKeyboardButton]:
    row: list[InlineKeyboardButton] = []
    if back:
        row.append(InlineKeyboardButton(text="◀️ Назад", callback_data=back))
    row.append(InlineKeyboardButton(text="🔄 Обновить", callback_data=refresh))
    return row


def _pager(
    *, prefix: str, page: int, pages: int
) -> list[InlineKeyboardButton] | None:
    if pages <= 1:
        return None
    prev_p = max(0, page - 1)
    next_p = min(pages - 1, page + 1)
    return [
        InlineKeyboardButton(text="←", callback_data=f"{prefix}:{prev_p}"),
        InlineKeyboardButton(text=f"{page + 1}/{pages}", callback_data=f"{prefix}:{page}"),
        InlineKeyboardButton(text="→", callback_data=f"{prefix}:{next_p}"),
    ]


def kb_main(*, open_bugs: int = 0) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="👥 Пользователи", callback_data=f"{CB_USERS}:0"),
            InlineKeyboardButton(text="✈️ Отслеживания", callback_data=f"{CB_WATCHES}:0"),
        ],
        [
            InlineKeyboardButton(text="📊 Воронка", callback_data=CB_FUNNEL),
            InlineKeyboardButton(text="🔔 Уведомления", callback_data=f"{CB_ALERTS}:0"),
        ],
        [InlineKeyboardButton(text="⚙️ Система", callback_data=CB_SYSTEM)],
    ]
    if open_bugs > 0:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🐞 Баги ({open_bugs})", callback_data=f"{CB_BUGS}:0"
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="🔄 Обновить", callback_data=CB_MAIN)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_main(summary: stats.MainSummary) -> str:
    lines = [
        "🛠 <b>FlyPing Admin</b>",
        "",
        f"Пользователи: <b>{summary.users}</b>",
        f"Активные отслеживания: <b>{summary.active_watches}</b>",
        f"Уведомлений за 24ч: <b>{summary.alerts_24h}</b>",
        f"Новых за 24ч: <b>{summary.new_users_24h}</b>",
    ]
    if summary.open_bugs:
        lines.append(f"🐞 Bugs open: <b>{summary.open_bugs}</b>")
    return "\n".join(lines)


def format_users(summary: stats.UsersSummary, tz: ZoneInfo) -> str:
    lines = [
        "👥 <b>Пользователи</b>",
        "",
        f"Всего: <b>{summary.total}</b>",
        f"Новых за 24ч: <b>{summary.new_24h}</b>",
        f"Новых за 7 дней: <b>{summary.new_7d}</b>",
        f"С отслеживаниями: <b>{summary.with_watches}</b>",
        f"С активными отслеживаниями: <b>{summary.with_active_watches}</b>",
        f"Получили хотя бы 1 alert: <b>{summary.with_alerts}</b>",
        "",
    ]
    if not summary.items:
        lines.append("Пока нет пользователей.")
    else:
        for i, item in enumerate(summary.items, start=summary.page * stats.PAGE_SIZE + 1):
            name = _display_name(item.get("username"))
            cohort = item.get("cohort")
            cohort_s = f" · cohort: {escape(str(cohort))}" if cohort else ""
            lines.append(f"{i}. {name}")
            lines.append(f"   {_fmt_dt(item.get('created_at'), tz)}")
            lines.append(f"   source: {escape(str(item.get('source') or 'direct'))}{cohort_s}")
            lines.append(
                f"   watches: {item.get('watches', 0)} · active: {item.get('active_watches', 0)}"
                f" · alerts: {item.get('alerts', 0)}"
            )
            lines.append("")
    lines.append(f"<i>время: {escape(str(tz))}</i>")
    return "\n".join(lines).rstrip()


def kb_users(summary: stats.UsersSummary) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for item in summary.items:
        label = item.get("username") or f"user#{item['id']}"
        if item.get("username"):
            label = f"@{item['username']}"
        else:
            label = f"id:{item['id']}"  # internal db id only, not telegram
        # keep button short
        if len(label) > 28:
            label = label[:27] + "…"
        rows.append(
            [
                InlineKeyboardButton(
                    text=label, callback_data=f"{CB_USER}:{int(item['id'])}"
                )
            ]
        )
    pager = _pager(prefix=CB_USERS, page=summary.page, pages=summary.pages)
    if pager:
        rows.append(pager)
    rows.append(_nav_row(back=CB_MAIN, refresh=f"{CB_USERS}:{summary.page}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_user_detail(detail: dict, tz: ZoneInfo) -> str:
    name = _display_name(detail.get("username"))
    lines = [
        f"👤 {name}",
        "",
        f"First seen: {_fmt_dt(detail.get('created_at'), tz)}",
        f"Source: {escape(str(detail.get('source') or 'direct'))}",
        f"Last source: {escape(str(detail.get('last_source') or '—'))}",
        f"Beta cohort: {escape(str(detail.get('cohort') or '—'))}",
        f"Consent: {_fmt_dt(detail.get('consent_at'), tz)}",
        "",
        f"Watches: {detail.get('watches', 0)}",
        f"Active watches: {detail.get('active_watches', 0)}",
        f"Alerts: {detail.get('alerts', 0)}",
        "",
        f"First watch: {_fmt_dt(detail.get('first_watch'), tz)}",
        f"Last watch: {_fmt_dt(detail.get('last_watch'), tz)}",
        f"First alert: {_fmt_dt(detail.get('first_alert'), tz)}",
        f"Last alert: {_fmt_dt(detail.get('last_alert'), tz)}",
        "",
        f"Survey A: {escape(str(detail.get('survey_a') or '—'))}",
        f"Bugs: {detail.get('bugs_open', 0)}",
        "",
        f"<i>время: {escape(str(tz))}</i>",
    ]
    return "\n".join(lines)


def kb_user_detail(user_id: int, *, back_page: int = 0) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            _nav_row(back=f"{CB_USERS}:{back_page}", refresh=f"{CB_USER}:{user_id}"),
        ]
    )


def format_watches(summary: stats.WatchesSummary, tz: ZoneInfo) -> str:
    lines = [
        "✈️ <b>Отслеживания</b>",
        "",
        f"Всего: <b>{summary.total}</b>",
        f"Активных: <b>{summary.active}</b>",
        f"Создано за 24ч: <b>{summary.created_24h}</b>",
        f"Создано за 7 дней: <b>{summary.created_7d}</b>",
        "",
    ]
    if not summary.items:
        lines.append("Пока нет отслеживаний.")
    else:
        for item in summary.items:
            route = f"{escape(str(item['origin']))} → {escape(str(item['destination']))}"
            if item.get("return_date"):
                dates = f"{_fmt_date(item.get('depart_date'))}–{_fmt_date(item.get('return_date'))}"
            else:
                dates = _fmt_date(item.get("depart_date"))
            status = "✅ Активно" if item.get("is_active") else "⏸ Выключено"
            lines.append(route)
            lines.append(dates)
            if item.get("last_price") is not None:
                lines.append(
                    f"Посл. цена: ≈ {money(item['last_price'], item.get('currency') or 'RUB')}"
                )
            lines.append(
                f"Желаемая цена: {money(item['max_price'], item.get('currency') or 'RUB')}"
            )
            lines.append(_display_name(item.get("username")))
            lines.append(status)
            lines.append(f"Создано: {_fmt_dt(item.get('created_at'), tz)}")
            lines.append("")
    lines.append(f"<i>время: {escape(str(tz))}</i>")
    return "\n".join(lines).rstrip()


def kb_watches(summary: stats.WatchesSummary) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pager = _pager(prefix=CB_WATCHES, page=summary.page, pages=summary.pages)
    if pager:
        rows.append(pager)
    rows.append(_nav_row(back=CB_MAIN, refresh=f"{CB_WATCHES}:{summary.page}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_funnel(summary: stats.FunnelSummary) -> str:
    watch_pct = _pct(summary.with_watch, summary.users)
    alert_of_watch = _pct(summary.with_alert, summary.with_watch)
    alert_of_all = _pct(summary.with_alert, summary.users)
    return "\n".join(
        [
            "📊 <b>Воронка</b>",
            "",
            f"Всего пользователей: <b>{summary.users}</b>",
            "",
            f"Создали watch: <b>{summary.with_watch}</b>",
            f"{watch_pct}",
            "",
            f"Получили хотя бы 1 alert: <b>{summary.with_alert}</b>",
            f"{alert_of_watch} от создавших watch",
            f"{alert_of_all} от всех пользователей",
            "",
            f"Активные watches: <b>{summary.active_watches}</b>",
            "",
            "За последние 7 дней:",
            f"Новые пользователи: <b>{summary.new_users_7d}</b>",
            f"Создали первый watch: <b>{summary.first_watch_7d}</b>",
            f"Получили первый alert: <b>{summary.first_alert_7d}</b>",
        ]
    )


def kb_funnel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Источники", callback_data=CB_SOURCES)],
            _nav_row(back=CB_MAIN, refresh=CB_FUNNEL),
        ]
    )


def format_sources(buckets: list[stats.SourceBucket]) -> str:
    lines = ["🔗 <b>Источники</b>", "", "<i>first-touch (first_start_source)</i>", ""]
    if not buckets:
        lines.append("Нет данных.")
        return "\n".join(lines)
    for b in buckets:
        lines.append(escape(b.key))
        lines.append(f"users: {b.users}")
        lines.append(f"watch: {b.with_watch}")
        lines.append(f"alert: {b.with_alert}")
        lines.append("")
    return "\n".join(lines).rstrip()


def kb_sources() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_nav_row(back=CB_FUNNEL, refresh=CB_SOURCES)]
    )


def format_alerts(summary: stats.AlertsSummary, tz: ZoneInfo) -> str:
    lines = [
        "🔔 <b>Уведомления</b>",
        "",
        f"За 24ч: <b>{summary.last_24h}</b>",
        f"За 7 дней: <b>{summary.last_7d}</b>",
        f"Всего: <b>{summary.total}</b>",
        f"Уникальных пользователей с alert: <b>{summary.unique_users}</b>",
        "",
    ]
    if not summary.items:
        lines.append("Пока нет уведомлений.")
    else:
        for item in summary.items:
            lines.append(_display_name(item.get("username")))
            lines.append(
                f"{escape(str(item.get('origin')))} → {escape(str(item.get('destination')))}"
            )
            lines.append(
                f"Найденная цена: {money(item['price'], item.get('currency') or 'RUB')}"
            )
            lines.append(
                f"Порог: {money(item['threshold'], item.get('currency') or 'RUB')}"
            )
            lines.append(_fmt_dt(item.get("sent_at"), tz))
            lines.append("")
    lines.append(f"<i>время: {escape(str(tz))}</i>")
    return "\n".join(lines).rstrip()


def kb_alerts(summary: stats.AlertsSummary) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pager = _pager(prefix=CB_ALERTS, page=summary.page, pages=summary.pages)
    if pager:
        rows.append(pager)
    rows.append(_nav_row(back=CB_MAIN, refresh=f"{CB_ALERTS}:{summary.page}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


def format_system(summary: stats.SystemSummary, tz: ZoneInfo) -> str:
    def line(label: str, ok: bool | None) -> str:
        icon = _status_icon(ok)
        if ok is None:
            return f"{label}: {icon} Нет данных"
        return f"{label}: {icon}"

    lines = [
        "⚙️ <b>Система</b>",
        "",
        line("API", summary.api_ok),
        line("Bot", summary.bot_ok),
        line("Checker", summary.checker_ok),
        line("Beta dispatcher", summary.beta_dispatcher_ok),
        line("Database", summary.database_ok),
        "",
        f"Version: {escape(summary.version)}",
        "",
        f"Last checker: {_fmt_dt(summary.last_checker_at, tz)}",
        f"Next checker: {_fmt_dt(summary.next_checker_at, tz)}",
        f"Active watches: {summary.active_watches}",
        "",
        f"Last beta dispatcher: {_fmt_dt(summary.last_beta_dispatcher_at, tz)}",
    ]
    if summary.beta_enabled:
        lines.append(
            f"<i>beta interval: {summary.beta_interval_seconds}s · "
            f"checker interval: {summary.checker_interval_seconds}s</i>"
        )
    else:
        lines.append("<i>beta dispatcher выключен (BETA_ENABLED=false)</i>")
    lines.append("")
    lines.append(f"<i>время: {escape(str(tz))}</i>")
    return "\n".join(lines)


def kb_system() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[_nav_row(back=CB_MAIN, refresh=CB_SYSTEM)]
    )


def format_bugs(
    total: int, page: int, pages: int, items: list[dict], tz: ZoneInfo
) -> str:
    lines = [f"🐞 <b>Баги</b> (open: {total})", ""]
    if not items:
        lines.append("Открытых багов нет.")
    else:
        for item in items:
            lines.append(
                f"{escape(str(item.get('severity') or '?'))} · {_display_name(item.get('username'))}"
            )
            lines.append(_fmt_dt(item.get("created_at"), tz))
            text = escape(str(item.get("what_happened") or "—"))
            lines.append(text)
            lines.append(f"status: {escape(str(item.get('status') or 'open'))}")
            lines.append("")
    lines.append(f"<i>время: {escape(str(tz))} · страница {page + 1}/{pages}</i>")
    return "\n".join(lines).rstrip()


def kb_bugs(page: int, pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    pager = _pager(prefix=CB_BUGS, page=page, pages=pages)
    if pager:
        rows.append(pager)
    rows.append(_nav_row(back=CB_MAIN, refresh=f"{CB_BUGS}:{page}"))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _safe_edit_or_answer(
    *,
    message: Message | None,
    callback: CallbackQuery | None,
    text: str,
    reply_markup: InlineKeyboardMarkup,
) -> None:
    if callback and callback.message:
        try:
            await callback.message.edit_text(
                text, parse_mode="HTML", reply_markup=reply_markup
            )
            return
        except Exception:
            logger.debug("admin edit_text failed; fallback answer", exc_info=True)
            try:
                await callback.message.answer(
                    text, parse_mode="HTML", reply_markup=reply_markup
                )
                return
            except Exception:
                logger.exception("admin fallback answer failed")
                return
    if message:
        await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)


def create_admin_dashboard_router(settings: Settings, bot: Bot) -> Router:
    """Bot param kept for signature symmetry with other routers; unused."""
    _ = bot
    router = Router(name="admin_dashboard")
    tz = settings.display_tz

    async def _deny_callback(callback: CallbackQuery) -> None:
        await callback.answer("Нет доступа", show_alert=False)

    def _admin_from_message(message: Message) -> bool:
        user = message.from_user
        return _is_admin_user(user.id if user else None, settings)

    def _admin_from_callback(callback: CallbackQuery) -> bool:
        user = callback.from_user
        return _is_admin_user(user.id if user else None, settings)

    async def render_main(
        *, message: Message | None = None, callback: CallbackQuery | None = None
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_main_summary(session)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_main(summary),
                reply_markup=kb_main(open_bugs=summary.open_bugs),
            )
        except Exception:
            logger.exception("admin main failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=kb_main(),
            )

    async def render_users(
        page: int,
        *,
        message: Message | None = None,
        callback: CallbackQuery | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_users_summary(session, page=page)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_users(summary, tz),
                reply_markup=kb_users(summary),
            )
        except Exception:
            logger.exception("admin users failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=CB_MAIN, refresh=f"{CB_USERS}:0")]
                ),
            )

    async def render_user_detail(
        user_id: int,
        *,
        message: Message | None = None,
        callback: CallbackQuery | None = None,
        username: str | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                detail = await stats.fetch_user_detail(
                    session, user_id=user_id if username is None else None, username=username
                )
            if detail is None:
                text = "Пользователь не найден"
                markup = InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=f"{CB_USERS}:0", refresh=CB_MAIN)]
                )
            else:
                text = format_user_detail(detail, tz)
                markup = kb_user_detail(int(detail["id"]))
            await _safe_edit_or_answer(
                message=message, callback=callback, text=text, reply_markup=markup
            )
        except Exception:
            logger.exception("admin user detail failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=f"{CB_USERS}:0", refresh=CB_MAIN)]
                ),
            )

    async def render_watches(
        page: int,
        *,
        message: Message | None = None,
        callback: CallbackQuery | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_watches_summary(session, page=page)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_watches(summary, tz),
                reply_markup=kb_watches(summary),
            )
        except Exception:
            logger.exception("admin watches failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=CB_MAIN, refresh=f"{CB_WATCHES}:0")]
                ),
            )

    async def render_funnel(
        *, message: Message | None = None, callback: CallbackQuery | None = None
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_funnel_summary(session)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_funnel(summary),
                reply_markup=kb_funnel(),
            )
        except Exception:
            logger.exception("admin funnel failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=kb_funnel(),
            )

    async def render_sources(
        *, message: Message | None = None, callback: CallbackQuery | None = None
    ) -> None:
        try:
            async with session_scope() as session:
                buckets = await stats.fetch_source_buckets(session)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_sources(buckets),
                reply_markup=kb_sources(),
            )
        except Exception:
            logger.exception("admin sources failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=kb_sources(),
            )

    async def render_alerts(
        page: int,
        *,
        message: Message | None = None,
        callback: CallbackQuery | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_alerts_summary(session, page=page)
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_alerts(summary, tz),
                reply_markup=kb_alerts(summary),
            )
        except Exception:
            logger.exception("admin alerts failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=CB_MAIN, refresh=f"{CB_ALERTS}:0")]
                ),
            )

    async def render_system(
        *, message: Message | None = None, callback: CallbackQuery | None = None
    ) -> None:
        try:
            async with session_scope() as session:
                summary = await stats.fetch_system_summary(
                    session,
                    version=get_version(),
                    beta_enabled=bool(settings.beta_enabled),
                    checker_interval_seconds=int(settings.poll_interval_seconds),
                    beta_interval_seconds=int(settings.beta_dispatcher_interval_seconds),
                    checker_stale_after_seconds=int(
                        settings.effective_checker_stale_after_seconds
                    ),
                )
            # Bot is live if we are handling this request.
            summary = stats.SystemSummary(
                api_ok=summary.api_ok,
                bot_ok=True,
                checker_ok=summary.checker_ok,
                beta_dispatcher_ok=None,  # no heartbeat — unknown, not false green
                database_ok=summary.database_ok,
                version=summary.version,
                last_checker_at=summary.last_checker_at,
                next_checker_at=summary.next_checker_at,
                active_watches=summary.active_watches,
                last_beta_dispatcher_at=None,
                beta_enabled=summary.beta_enabled,
                checker_interval_seconds=summary.checker_interval_seconds,
                beta_interval_seconds=summary.beta_interval_seconds,
            )
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_system(summary, tz),
                reply_markup=kb_system(),
            )
        except Exception:
            logger.exception("admin system failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=kb_system(),
            )

    async def render_bugs(
        page: int,
        *,
        message: Message | None = None,
        callback: CallbackQuery | None = None,
    ) -> None:
        try:
            async with session_scope() as session:
                total, page_n, pages, items = await stats.fetch_open_bugs(
                    session, page=page
                )
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text=format_bugs(total, page_n, pages, items, tz),
                reply_markup=kb_bugs(page_n, pages),
            )
        except Exception:
            logger.exception("admin bugs failed")
            await _safe_edit_or_answer(
                message=message,
                callback=callback,
                text="⚠️ Не удалось получить данные",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[_nav_row(back=CB_MAIN, refresh=f"{CB_BUGS}:0")]
                ),
            )

    @router.message(Command("admin"))
    async def cmd_admin(message: Message) -> None:
        if not _admin_from_message(message):
            return
        await render_main(message=message)

    @router.message(Command("user"))
    async def cmd_user(message: Message, command: CommandObject) -> None:
        if not _admin_from_message(message):
            return
        arg = (command.args or "").strip()
        if not arg:
            await message.answer("Использование: <code>/user @username</code>", parse_mode="HTML")
            return
        await render_user_detail(0, message=message, username=arg)

    @router.callback_query(F.data.startswith("ad:"))
    async def on_admin_callback(callback: CallbackQuery) -> None:
        if not _admin_from_callback(callback):
            await _deny_callback(callback)
            return
        data = callback.data or ""
        await callback.answer()
        try:
            if data == CB_MAIN:
                await render_main(callback=callback)
            elif data == CB_FUNNEL:
                await render_funnel(callback=callback)
            elif data == CB_SOURCES:
                await render_sources(callback=callback)
            elif data == CB_SYSTEM:
                await render_system(callback=callback)
            elif data.startswith(f"{CB_USERS}:"):
                page = int(data.rsplit(":", 1)[-1])
                await render_users(page, callback=callback)
            elif data.startswith(f"{CB_USER}:"):
                uid = int(data.rsplit(":", 1)[-1])
                await render_user_detail(uid, callback=callback)
            elif data.startswith(f"{CB_WATCHES}:"):
                page = int(data.rsplit(":", 1)[-1])
                await render_watches(page, callback=callback)
            elif data.startswith(f"{CB_ALERTS}:"):
                page = int(data.rsplit(":", 1)[-1])
                await render_alerts(page, callback=callback)
            elif data.startswith(f"{CB_BUGS}:"):
                page = int(data.rsplit(":", 1)[-1])
                await render_bugs(page, callback=callback)
            else:
                await render_main(callback=callback)
        except Exception:
            logger.exception("admin callback failed data=%s", data)
            try:
                if callback.message:
                    await callback.message.answer("⚠️ Не удалось получить данные")
            except Exception:
                pass

    return router
