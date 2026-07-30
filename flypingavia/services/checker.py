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
from flypingavia.services.notify_policy import decide_notification
from flypingavia.services.prices import PriceProvider, align_band_to_quote, build_affiliate_url

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
        async with session_scope() as session:
            watches = list(await repo.get_active_watches(session))

        for watch in watches:
            telegram_id = watch.user.telegram_id
            try:
                quote = await self.provider.get_trip_quote(
                    watch.origin_codes,
                    watch.destination_codes,
                    depart_date=watch.depart_date,
                    return_date=watch.return_date,
                    adults=watch.adults,
                    children=watch.children,
                    infants=watch.infants,
                    currency=watch.currency.lower(),
                )
                band = await self.provider.get_trip_band(
                    watch.origin_codes,
                    watch.destination_codes,
                    depart_date=watch.depart_date,
                    return_date=watch.return_date,
                    adults=watch.adults,
                    children=watch.children,
                    infants=watch.infants,
                    currency=watch.currency.lower(),
                )
                band = align_band_to_quote(band, quote)
            except Exception:
                logger.exception("Не удалось получить цену для watch_id=%s", watch.id)
                continue

            if quote is None:
                continue

            below_threshold = False
            snapshot: Watch | None = None
            decision_allow = False

            async with session_scope() as session:
                fresh = await session.get(Watch, watch.id)
                if fresh is None or not fresh.is_active:
                    continue

                fresh.last_price = quote.price
                fresh.last_checked_at = datetime.now(timezone.utc)
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
                        "%s watch_id=%s price=%s threshold=%s",
                        decision.log_message,
                        fresh.id,
                        quote.price,
                        fresh.max_price,
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
                    last_price=fresh.last_price,
                    last_origin_airport=fresh.last_origin_airport,
                    last_destination_airport=fresh.last_destination_airport,
                    is_active=fresh.is_active,
                )

            if not below_threshold or not decision_allow or snapshot is None:
                continue

            link = build_affiliate_url(
                snapshot.origin,
                snapshot.destination,
                self.settings.affiliate_marker,
                snapshot.depart_date,
                return_date=snapshot.return_date,
                adults=snapshot.adults,
                children=snapshot.children,
                infants=snapshot.infants,
            )
            text = fmt.format_price_card(
                origin=snapshot.origin,
                destination=snapshot.destination,
                depart_date=snapshot.depart_date,
                quote=quote,
                band=band,
                threshold=snapshot.max_price,
                title="🔔 Цена ≤ порога",
                watch_id=snapshot.id,
                origin_name=snapshot.origin_name,
                destination_name=snapshot.destination_name,
                return_date=snapshot.return_date,
                adults=snapshot.adults,
                children=snapshot.children,
                infants=snapshot.infants,
                threshold_contract=True,
            )

            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb.watch_actions_kb(snapshot.id, link),
                    disable_web_page_preview=True,
                )
            except Exception:
                logger.exception("Telegram send failed user=%s", telegram_id)
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

        return alerts
