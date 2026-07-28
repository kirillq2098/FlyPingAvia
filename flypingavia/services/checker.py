from __future__ import annotations

import logging
from datetime import datetime, timezone

from aiogram import Bot
from aiogram.enums import ParseMode

from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.models import Watch
from flypingavia.db.session import session_scope
from flypingavia.services.prices import PriceProvider, build_affiliate_url

logger = logging.getLogger(__name__)


class PriceChecker:
    def __init__(self, bot: Bot, settings: Settings, provider: PriceProvider) -> None:
        self.bot = bot
        self.settings = settings
        self.provider = provider

    async def run_once(self) -> int:
        """Проверяет все активные подписки. Возвращает число отправленных алертов."""
        alerts = 0
        async with session_scope() as session:
            watches = list(await repo.get_active_watches(session))

        for watch in watches:
            telegram_id = watch.user.telegram_id
            try:
                quote = await self.provider.get_cheapest(
                    origin=watch.origin,
                    destination=watch.destination,
                    depart_date=watch.depart_date,
                    currency=watch.currency.lower(),
                )
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
                # Пока без антиспама: алерт при каждом попадании под порог
                should_alert = quote.price <= fresh.max_price
                if should_alert:
                    fresh.last_alert_price = quote.price

                await session.flush()
                snapshot = Watch(
                    id=fresh.id,
                    user_id=fresh.user_id,
                    origin=fresh.origin,
                    destination=fresh.destination,
                    max_price=fresh.max_price,
                    depart_date=fresh.depart_date,
                    currency=fresh.currency,
                    last_price=fresh.last_price,
                    is_active=fresh.is_active,
                )

            if not should_alert or snapshot is None:
                continue

            link = build_affiliate_url(
                origin=snapshot.origin,
                destination=snapshot.destination,
                marker=self.settings.affiliate_marker,
                depart_date=snapshot.depart_date,
            )
            transfers = (
                f", пересадок: {quote.transfers}"
                if quote.transfers is not None
                else ""
            )
            price_fmt = f"{int(quote.price):,}".replace(",", " ")
            max_fmt = f"{int(snapshot.max_price):,}".replace(",", " ")
            text = (
                f"🔔 <b>Цена ниже порога!</b>\n"
                f"{snapshot.route_label}\n"
                f"Сейчас: <b>{price_fmt} {quote.currency}</b>{transfers}\n"
                f"Ваш порог: {max_fmt} {snapshot.currency}\n"
                f'<a href="{link}">Смотреть билеты</a>'
            )

            try:
                await self.bot.send_message(
                    chat_id=telegram_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                )
                alerts += 1
            except Exception:
                logger.exception("Не удалось отправить алерт user=%s", telegram_id)

        return alerts
