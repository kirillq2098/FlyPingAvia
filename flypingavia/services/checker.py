from __future__ import annotations

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
from flypingavia.services.prices import PriceProvider, align_band_to_quote, build_affiliate_url

logger = logging.getLogger(__name__)


class PriceChecker:
    def __init__(self, bot: Bot, settings: Settings, provider: PriceProvider) -> None:
        self.bot = bot
        self.settings = settings
        self.provider = provider

    async def run_once(self) -> int:
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

            should_alert = False
            snapshot: Watch | None = None

            async with session_scope() as session:
                fresh = await session.get(Watch, watch.id)
                if fresh is None or not fresh.is_active:
                    continue

                fresh.last_price = quote.price
                fresh.last_checked_at = datetime.now(timezone.utc)
                fresh.last_origin_airport = quote.origin_code
                fresh.last_destination_airport = quote.destination_code
                should_alert = quote.price <= fresh.max_price
                if should_alert:
                    fresh.last_alert_price = quote.price

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

            if not should_alert or snapshot is None:
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
                title="Цена ниже порога!",
                watch_id=snapshot.id,
                origin_name=snapshot.origin_name,
                destination_name=snapshot.destination_name,
                return_date=snapshot.return_date,
                adults=snapshot.adults,
                children=snapshot.children,
                infants=snapshot.infants,
            )

            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=kb.watch_actions_kb(snapshot.id, link),
                    disable_web_page_preview=True,
                )
                alerts += 1
            except Exception:
                logger.exception("Не удалось отправить алерт user=%s", telegram_id)

        return alerts
