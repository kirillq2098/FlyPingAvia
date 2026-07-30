"""CS-07 MVP: окно гибких дат вокруг основной даты Watch."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Optional, Sequence

from flypingavia.services.prices import (
    PriceBand,
    PriceProvider,
    PriceQuote,
    align_band_to_quote,
)

logger = logging.getLogger(__name__)

ALLOWED_FLEXIBILITY_DAYS = frozenset({0, 1, 3, 7})
DEFAULT_SEARCH_CONCURRENCY = 3


@dataclass(frozen=True)
class DateCandidate:
    depart_date: date
    return_date: date | None
    offset_days: int


@dataclass(frozen=True)
class FlexibleTripResult:
    quote: PriceQuote
    found_depart_date: date | None
    found_return_date: date | None
    offset_days: int
    primary_depart_date: date | None
    primary_return_date: date | None
    flexibility_days: int
    band: PriceBand | None = None


def validate_flexibility_days(value: int | float | None) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("flexibility_days must be an integer in {0, 1, 3, 7}")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("flexibility_days must be an integer in {0, 1, 3, 7}")
    days = int(value)
    if days not in ALLOWED_FLEXIBILITY_DAYS:
        raise ValueError("flexibility_days must be one of 0, 1, 3, 7")
    return days


def build_date_candidates(
    depart_date: date,
    return_date: date | None,
    flexibility_days: int,
    *,
    today: date | None = None,
) -> list[DateCandidate]:
    """Кандидаты от −N до +N; RT сдвигает обе даты одинаково; прошлые отбрасываются."""
    days = validate_flexibility_days(flexibility_days)
    today = today or date.today()
    trip_len: int | None = None
    if return_date is not None:
        trip_len = (return_date - depart_date).days
        if trip_len < 0:
            raise ValueError("return_date earlier than depart_date")

    candidates: list[DateCandidate] = []
    for offset in range(-days, days + 1):
        dep = depart_date + timedelta(days=offset)
        if dep < today:
            continue
        ret: date | None = None
        if trip_len is not None:
            ret = dep + timedelta(days=trip_len)
        candidates.append(DateCandidate(depart_date=dep, return_date=ret, offset_days=offset))
    return candidates


async def search_flexible_trip(
    provider: PriceProvider,
    *,
    origins: Sequence[str],
    destinations: Sequence[str],
    depart_date: Optional[date],
    return_date: Optional[date] = None,
    flexibility_days: int = 0,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    currency: str = "rub",
    concurrency: int = DEFAULT_SEARCH_CONCURRENCY,
    today: date | None = None,
) -> FlexibleTripResult | None:
    """Ищет минимальную цену по окну дат; возвращает Quote с фактическими датами."""
    flex = validate_flexibility_days(flexibility_days)

    # «Любая дата» или без основной даты — один поиск как раньше.
    if depart_date is None or flex == 0:
        try:
            quote = await provider.get_trip_quote(
                origins,
                destinations,
                depart_date=depart_date,
                return_date=return_date,
                adults=adults,
                children=children,
                infants=infants,
                currency=currency,
            )
        except Exception:
            logger.exception(
                "Flexible search provider error primary_depart=%s",
                depart_date,
            )
            return None
        if quote is None:
            logger.info("Flexible search: no offers for primary_depart=%s", depart_date)
            return None
        band = None
        try:
            band = await provider.get_trip_band(
                origins,
                destinations,
                depart_date=depart_date,
                return_date=return_date,
                adults=adults,
                children=children,
                infants=infants,
                currency=currency,
            )
            band = align_band_to_quote(band, quote)
        except Exception:
            logger.exception("Flexible search band error primary_depart=%s", depart_date)
            band = None
        found_dep = depart_date
        found_ret = return_date if return_date is not None else quote.return_date
        # enrich quote with return if missing
        if found_ret is not None and quote.return_date is None:
            quote = replace(quote, return_date=found_ret)
        return FlexibleTripResult(
            quote=quote,
            found_depart_date=found_dep,
            found_return_date=found_ret,
            offset_days=0,
            primary_depart_date=depart_date,
            primary_return_date=return_date,
            flexibility_days=flex,
            band=band,
        )

    candidates = build_date_candidates(
        depart_date,
        return_date,
        flex,
        today=today,
    )
    if not candidates:
        logger.info(
            "Flexible search: empty window after past filter primary=%s flex=%s",
            depart_date,
            flex,
        )
        return None

    sem = asyncio.Semaphore(max(1, int(concurrency)))

    async def _one(cand: DateCandidate) -> tuple[DateCandidate, PriceQuote | None, Exception | None]:
        async with sem:
            try:
                quote = await provider.get_trip_quote(
                    origins,
                    destinations,
                    depart_date=cand.depart_date,
                    return_date=cand.return_date,
                    adults=adults,
                    children=children,
                    infants=infants,
                    currency=currency,
                )
                if quote is None:
                    logger.info(
                        "Flexible search: no offers depart=%s return=%s offset=%s",
                        cand.depart_date,
                        cand.return_date,
                        cand.offset_days,
                    )
                    return cand, None, None
                return cand, quote, None
            except Exception as exc:
                logger.exception(
                    "Flexible search provider error depart=%s return=%s offset=%s",
                    cand.depart_date,
                    cand.return_date,
                    cand.offset_days,
                )
                return cand, None, exc

    results = await asyncio.gather(*[_one(c) for c in candidates])
    best: tuple[DateCandidate, PriceQuote] | None = None
    for cand, quote, _err in results:
        if quote is None:
            continue
        if best is None or quote.price < best[1].price:
            best = (cand, quote)

    if best is None:
        return None

    cand, quote = best
    found_ret = cand.return_date if cand.return_date is not None else quote.return_date
    if found_ret is not None and quote.return_date != found_ret:
        quote = replace(quote, return_date=found_ret)

    band = None
    try:
        band = await provider.get_trip_band(
            origins,
            destinations,
            depart_date=cand.depart_date,
            return_date=cand.return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=currency,
        )
        band = align_band_to_quote(band, quote)
    except Exception:
        logger.exception(
            "Flexible search band error found_depart=%s",
            cand.depart_date,
        )
        band = None

    return FlexibleTripResult(
        quote=quote,
        found_depart_date=cand.depart_date,
        found_return_date=found_ret,
        offset_days=cand.offset_days,
        primary_depart_date=depart_date,
        primary_return_date=return_date,
        flexibility_days=flex,
        band=band,
    )
