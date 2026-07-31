from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.enums import ParseMode

from flypingavia.bot import formatters as fmt
from flypingavia.bot import keyboards as kb
from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.models import Watch
from flypingavia.db.session import session_scope
from flypingavia.monitoring.heartbeat import (
    mark_checker_error,
    mark_checker_started,
    mark_checker_success,
)
from flypingavia.monitoring.keys import INCIDENT_PROVIDER, INCIDENT_TELEGRAM
from flypingavia.monitoring.notify import notify_failure, notify_recovery
from flypingavia.monitoring.telegram_errors import classify_telegram_send_error, SYSTEM
from flypingavia.services.flexible_dates import search_flexible_trip
from flypingavia.services.notify_policy import decide_notification
from flypingavia.services.prices import PriceProvider, build_affiliate_url

logger = logging.getLogger(__name__)


class PriceChecker:
    def __init__(self, bot: Bot, settings: Settings, provider: PriceProvider) -> None:
        self.bot = bot
        self.settings = settings
        self.provider = provider
        self._run_lock = asyncio.Lock()

    async def run_once(self) -> int:
        if self._run_lock.locked():
            logger.info("Price check skipped: another run is active")
            return 0

        async with self._run_lock:
            return await self._run_once_locked()

    async def _run_once_locked(self) -> int:
        alerts = 0
        now = datetime.now(timezone.utc)
        async with session_scope() as session:
            await mark_checker_started(session, at=now)
            watches = list(await repo.get_active_watches(session))

        if not watches:
            async with session_scope() as session:
                await mark_checker_success(session, at=datetime.now(timezone.utc))
            return 0

        provider_ok = 0
        provider_fail = 0
        system_tg_fail = 0
        tg_ok = 0
        last_provider_err = "provider error"

        for watch in watches:
            telegram_id = watch.user.telegram_id
            flex = int(getattr(watch, "flexibility_days", 0) or 0)
            try:
                result = await search_flexible_trip(
                    self.provider,
                    origins=watch.origin_codes,
                    destinations=watch.destination_codes,
                    depart_date=watch.depart_date,
                    return_date=watch.return_date,
                    flexibility_days=flex,
                    adults=watch.adults,
                    children=watch.children,
                    infants=watch.infants,
                    currency=watch.currency.lower(),
                )
            except Exception as exc:
                logger.exception("Не удалось получить цену для watch_id=%s", watch.id)
                provider_fail += 1
                last_provider_err = type(exc).__name__
                continue

            provider_ok += 1

            # Завершённая проверка (в т.ч. result=None) — фиксируем UTC now.
            checked_at = datetime.now(timezone.utc)

            if result is None or result.quote is None:
                async with session_scope() as session:
                    await repo.mark_watch_checked(session, watch.id, checked_at)
                continue

            quote = result.quote
            band = result.band
            found_depart = result.found_depart_date
            found_return = result.found_return_date
            offset_days = result.offset_days

            below_threshold = False
            snapshot: Watch | None = None
            decision_allow = False

            async with session_scope() as session:
                fresh = await session.get(Watch, watch.id)
                if fresh is None or not fresh.is_active:
                    continue

                fresh.last_price = quote.price
                fresh.last_checked_at = checked_at
                fresh.last_origin_airport = quote.origin_code
                fresh.last_destination_airport = quote.destination_code
                below_threshold = quote.price <= fresh.max_price

                if below_threshold:
                    last_event = await repo.get_latest_alert_event(session, fresh.id)
                    decision = decide_notification(
                        new_price=float(quote.price),
                        last_event=last_event,
                        cooldown_hours=self.settings.notification_cooldown_hours,
                        min_price_delta=self.settings.min_price_delta,
                    )
                    logger.info(
                        "%s watch_id=%s price=%s threshold=%s offset=%s",
                        decision.log_message,
                        fresh.id,
                        quote.price,
                        fresh.max_price,
                        offset_days,
                    )
                    decision_allow = decision.allow

                await session.flush()
                snapshot = Watch(
                    id=fresh.id,
                    user_id=fresh.user_id,
                    origin=fresh.origin,
                    destination=fresh.destination,
                    origin_name=fresh.origin_name,
                    destination_name=fresh.destination_name,
                    origin_search=fresh.origin_search,
                    destination_search=fresh.destination_search,
                    max_price=fresh.max_price,
                    depart_date=fresh.depart_date,
                    return_date=fresh.return_date,
                    adults=fresh.adults,
                    children=fresh.children,
                    infants=fresh.infants,
                    currency=fresh.currency,
                    flexibility_days=getattr(fresh, "flexibility_days", 0) or 0,
                    last_price=fresh.last_price,
                    last_origin_airport=fresh.last_origin_airport,
                    last_destination_airport=fresh.last_destination_airport,
                    last_checked_at=fresh.last_checked_at,
                    is_active=fresh.is_active,
                )

            if not below_threshold or not decision_allow or snapshot is None:
                continue

            link_depart = found_depart if found_depart is not None else snapshot.depart_date
            link_return = found_return if found_return is not None else snapshot.return_date
            link = build_affiliate_url(
                snapshot.origin,
                snapshot.destination,
                self.settings.affiliate_marker,
                link_depart,
                return_date=link_return,
                adults=snapshot.adults,
                children=snapshot.children,
                infants=snapshot.infants,
            )
            text = fmt.format_price_card(
                origin=snapshot.origin,
                destination=snapshot.destination,
                depart_date=link_depart,
                quote=quote,
                band=band,
                threshold=snapshot.max_price,
                title="🔔 Цена ≤ порога",
                watch_id=snapshot.id,
                origin_name=snapshot.origin_name,
                destination_name=snapshot.destination_name,
                return_date=link_return,
                adults=snapshot.adults,
                children=snapshot.children,
                infants=snapshot.infants,
                threshold_contract=True,
                found_depart_date=found_depart,
                found_return_date=found_return,
                offset_days=offset_days,
                primary_depart_date=snapshot.depart_date,
                primary_return_date=snapshot.return_date,
                flexibility_days=int(getattr(snapshot, "flexibility_days", 0) or 0),
                checked_at=checked_at,
                display_timezone=self.settings.display_tz,
                now=checked_at,
            )

            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb.watch_actions_kb(snapshot.id, link),
                    disable_web_page_preview=True,
                )
                tg_ok += 1
            except Exception as exc:
                logger.exception("Telegram send failed user=%s", telegram_id)
                if classify_telegram_send_error(exc) == SYSTEM:
                    system_tg_fail += 1
                continue

            try:
                async with session_scope() as session:
                    await repo.log_alert_event(
                        session,
                        watch_id=snapshot.id,
                        user_id=snapshot.user_id,
                        price=float(quote.price),
                        threshold=float(snapshot.max_price),
                        currency=snapshot.currency,
                    )
                    fresh = await session.get(Watch, snapshot.id)
                    if fresh is not None:
                        fresh.last_alert_price = float(quote.price)
                alerts += 1
            except Exception:
                logger.exception(
                    "Alert sent successfully but AlertEvent persistence failed "
                    "watch_id=%s user=%s",
                    snapshot.id,
                    telegram_id,
                )
                continue

        done_at = datetime.now(timezone.utc)
        if provider_ok > 0:
            async with session_scope() as session:
                await mark_checker_success(session, at=done_at)
            await notify_recovery(
                self.bot, self.settings, incident_key=INCIDENT_PROVIDER, recovered_at=done_at
            )
        else:
            async with session_scope() as session:
                await mark_checker_error(
                    session, at=done_at, summary=last_provider_err
                )
            if provider_fail > 0:
                await notify_failure(
                    self.bot,
                    self.settings,
                    incident_key=INCIDENT_PROVIDER,
                    summary=last_provider_err,
                    occurred_at=done_at,
                )

        if system_tg_fail > 0 and tg_ok == 0:
            await notify_failure(
                self.bot,
                self.settings,
                incident_key=INCIDENT_TELEGRAM,
                summary="system telegram delivery failures",
                occurred_at=done_at,
            )
        elif tg_ok > 0:
            await notify_recovery(
                self.bot, self.settings, incident_key=INCIDENT_TELEGRAM, recovered_at=done_at
            )

        return alerts
