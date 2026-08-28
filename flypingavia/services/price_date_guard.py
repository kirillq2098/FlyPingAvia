"""Defense-in-depth: quote departure date must match watch constraints."""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from flypingavia.services.flexible_dates import build_date_candidates, validate_flexibility_days

logger = logging.getLogger(__name__)


def quote_departure_matches_watch(
    *,
    watch_depart_date: Optional[date],
    candidate_depart_date: Optional[date],
    flexibility_days: int = 0,
    today: Optional[date] = None,
) -> tuple[bool, str]:
    """
    Return (allowed, reason).

    - no watch date: any candidate date allowed
    - flex=0: candidate must equal watch date exactly
    - flex>0: candidate must fall inside the flexible window
    """
    flex = validate_flexibility_days(flexibility_days)
    if watch_depart_date is None:
        return True, "no_watch_date"

    if candidate_depart_date is None:
        return False, "missing_candidate_date"

    if flex == 0:
        if candidate_depart_date == watch_depart_date:
            return True, "exact_match"
        logger.info(
            "candidate rejected reason=wrong_departure_date requested_date=%s candidate_date=%s",
            watch_depart_date.isoformat(),
            candidate_depart_date.isoformat(),
        )
        return False, "wrong_departure_date"

    allowed = {
        c.depart_date
        for c in build_date_candidates(
            watch_depart_date,
            None,
            flex,
            today=today or date.today(),
        )
    }
    if candidate_depart_date in allowed:
        return True, "within_flex_window"

    logger.info(
        "candidate rejected reason=outside_flex_window requested_date=%s candidate_date=%s flex=%s",
        watch_depart_date.isoformat(),
        candidate_depart_date.isoformat(),
        flex,
    )
    return False, "outside_flex_window"
