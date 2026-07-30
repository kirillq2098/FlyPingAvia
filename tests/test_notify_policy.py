from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from flypingavia.services.notify_policy import decide_notification


@dataclass
class _Evt:
    price: float
    sent_at: datetime


NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


def test_first_notification_allowed() -> None:
    d = decide_notification(
        new_price=15000,
        last_event=None,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is True
    assert d.reason == "first alert"
    assert d.log_message == "Notification allowed: first alert"


def test_cooldown_active_same_price_skipped() -> None:
    last = _Evt(price=15000, sent_at=NOW - timedelta(hours=2))
    d = decide_notification(
        new_price=15000,
        last_event=last,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is False
    assert d.reason == "cooldown active"
    assert d.log_message == "Notification skipped: cooldown active"


def test_cooldown_expired_allows_even_same_price() -> None:
    last = _Evt(price=15000, sent_at=NOW - timedelta(hours=25))
    d = decide_notification(
        new_price=15000,
        last_event=last,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is True
    assert d.reason == "cooldown expired"
    assert d.log_message == "Notification allowed: cooldown expired"


def test_price_delta_too_small_skipped() -> None:
    last = _Evt(price=15000, sent_at=NOW - timedelta(hours=1))
    d = decide_notification(
        new_price=14700,  # drop 300 < 500
        last_event=last,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is False
    assert d.reason == "price delta too small"
    assert d.log_message == "Notification skipped: price delta too small"


def test_price_dropped_significantly_allows_inside_cooldown() -> None:
    last = _Evt(price=15000, sent_at=NOW - timedelta(hours=1))
    d = decide_notification(
        new_price=14400,  # drop 600 >= 500
        last_event=last,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is True
    assert d.reason == "price dropped significantly"
    assert d.log_message == "Notification allowed: price dropped significantly"


def test_price_rise_inside_cooldown_skipped() -> None:
    last = _Evt(price=15000, sent_at=NOW - timedelta(hours=1))
    d = decide_notification(
        new_price=16000,
        last_event=last,
        cooldown_hours=24,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is False
    assert d.reason == "cooldown active"


@pytest.mark.parametrize(
    ("hours_ago", "cooldown", "expect_allow"),
    [
        (23.9, 24, False),
        (24.0, 24, True),
        (24.1, 24, True),
    ],
)
def test_cooldown_boundary(hours_ago: float, cooldown: float, expect_allow: bool) -> None:
    last = _Evt(price=10000, sent_at=NOW - timedelta(hours=hours_ago))
    d = decide_notification(
        new_price=10000,
        last_event=last,
        cooldown_hours=cooldown,
        min_price_delta=500,
        now=NOW,
    )
    assert d.allow is expect_allow
