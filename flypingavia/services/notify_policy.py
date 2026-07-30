"""NT-04: решение об отправке алерта по истории AlertEvent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional, Protocol


class _AlertLike(Protocol):
    price: float
    sent_at: datetime


@dataclass(frozen=True)
class NotifyDecision:
    allow: bool
    reason: str

    @property
    def log_message(self) -> str:
        prefix = "Notification allowed" if self.allow else "Notification skipped"
        return f"{prefix}: {self.reason}"


def decide_notification(
    *,
    new_price: float,
    last_event: Optional[_AlertLike],
    cooldown_hours: float,
    min_price_delta: float,
    now: datetime | None = None,
) -> NotifyDecision:
    """
    Отправлять алерт, если:
    - это первый AlertEvent по watch, или
    - истёк cooldown, или
    - цена упала минимум на min_price_delta относительно последнего алерта.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if last_event is None:
        return NotifyDecision(True, "first alert")

    sent_at = last_event.sent_at
    if sent_at.tzinfo is None:
        sent_at = sent_at.replace(tzinfo=timezone.utc)

    cooldown = timedelta(hours=max(0.0, float(cooldown_hours)))
    cooldown_expired = now >= sent_at + cooldown
    if cooldown_expired:
        return NotifyDecision(True, "cooldown expired")

    last_price = float(last_event.price)
    delta = max(0.0, float(min_price_delta))
    if new_price <= last_price - delta:
        return NotifyDecision(True, "price dropped significantly")

    if new_price < last_price:
        return NotifyDecision(False, "price delta too small")

    return NotifyDecision(False, "cooldown active")
