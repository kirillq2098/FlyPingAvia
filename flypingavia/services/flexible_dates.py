"""CS-07 MVP: окно гибких дат вокруг основной даты Watch."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Optional, Sequence

from flypingavia.services.prices import (
    PriceBand,
    PriceProvider,
    PriceQuote,
    align_band_to_quote,
    compute_price_band,
)

logger = logging.getLogger(__name__)

ALLOWED_FLEXIBILITY_DAYS = frozenset({0, 1, 3, 7})
DEFAULT_SEARCH_CONCURRENCY = 5
# Soft deadline for flexible fan-out (seconds from search start).
DEFAULT_SOFT_TIMEOUT_SECONDS = 9.0
DEFAULT_HARD_TIMEOUT_SECONDS = 18.0


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
    partial: bool = False
    combinations_count: int = 0
    completed_count: int = 0


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


def _band_from_quotes(
    quotes: Sequence[PriceQuote],
    *,
    currency: str,
) -> PriceBand | None:
    prices = [float(q.price) for q in quotes if q is not None and q.price and q.price > 0]
    return compute_price_band(prices, currency=currency, source="flexible_samples")


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
    soft_timeout_seconds: float | None = DEFAULT_SOFT_TIMEOUT_SECONDS,
    hard_timeout_seconds: float | None = DEFAULT_HARD_TIMEOUT_SECONDS,
) -> FlexibleTripResult | None:
    """Ищет минимальную цену по окну дат; возвращает Quote с фактическими датами."""
    flex = validate_flexibility_days(flexibility_days)
    started = time.monotonic()

    def _remaining_hard() -> float | None:
        if hard_timeout_seconds is None:
            return None
        return max(0.05, float(hard_timeout_seconds) - (time.monotonic() - started))

    def _past_soft() -> bool:
        if soft_timeout_seconds is None:
            return False
        return (time.monotonic() - started) >= float(soft_timeout_seconds)

    # «Любая дата» или без основной даты — один поиск как раньше.
    if depart_date is None or flex == 0:
        try:
            corr = _remaining_hard()
            if corr is not None:
                quote = await asyncio.wait_for(
                    provider.get_trip_quote(
                        origins,
                        destinations,
                        depart_date=depart_date,
                        return_date=return_date,
                        adults=adults,
                        children=children,
                        infants=infants,
                        currency=currency,
                    ),
                    timeout=corr,
                )
            else:
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
        except asyncio.TimeoutError:
            logger.info("Flexible search hard timeout primary_depart=%s", depart_date)
            return None
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
            rem = _remaining_hard()
            if rem is not None and rem < 0.4:
                band = _band_from_quotes([quote], currency=currency)
            else:
                if rem is not None:
                    band = await asyncio.wait_for(
                        provider.get_trip_band(
                            origins,
                            destinations,
                            depart_date=depart_date,
                            return_date=return_date,
                            adults=adults,
                            children=children,
                            infants=infants,
                            currency=currency,
                        ),
                        timeout=rem,
                    )
                else:
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
        except asyncio.TimeoutError:
            band = _band_from_quotes([quote], currency=currency)
        except Exception:
            logger.exception("Flexible search band error primary_depart=%s", depart_date)
            band = _band_from_quotes([quote], currency=currency)
        found_dep = depart_date
        found_ret = return_date if return_date is not None else quote.return_date
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
            partial=False,
            combinations_count=1,
            completed_count=1,
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

    # Primary date first, then nearest offsets — better partial results under soft timeout.
    candidates = sorted(
        candidates,
        key=lambda c: (0 if c.offset_days == 0 else 1, abs(c.offset_days), c.offset_days),
    )
    combinations_count = len(candidates)
    sem = asyncio.Semaphore(max(1, int(concurrency)))
    completed: list[tuple[DateCandidate, PriceQuote]] = []
    completed_lock = asyncio.Lock()
    stop = asyncio.Event()

    async def _one(cand: DateCandidate) -> None:
        if stop.is_set():
            return
        async with sem:
            if stop.is_set():
                return
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
                    return
                async with completed_lock:
                    completed.append((cand, quote))
            except Exception:
                logger.exception(
                    "Flexible search provider error depart=%s return=%s offset=%s",
                    cand.depart_date,
                    cand.return_date,
                    cand.offset_days,
                )

    tasks = [asyncio.create_task(_one(c)) for c in candidates]
    soft_task = None
    if soft_timeout_seconds is not None:

        async def _watch_soft() -> None:
            await asyncio.sleep(float(soft_timeout_seconds))
            async with completed_lock:
                has_any = bool(completed)
            if has_any:
                stop.set()

        soft_task = asyncio.create_task(_watch_soft())

    pending: set[asyncio.Task] = set(tasks)
    try:
        while pending:
            timeout = None
            if hard_timeout_seconds is not None:
                timeout = max(0.01, float(hard_timeout_seconds) - (time.monotonic() - started))
            done, pending = await asyncio.wait(
                pending,
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done and hard_timeout_seconds is not None:
                # hard timeout
                stop.set()
                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                pending = set()
                break
            if stop.is_set():
                async with completed_lock:
                    has_any = bool(completed)
                if has_any:
                    for t in pending:
                        t.cancel()
                    await asyncio.gather(*pending, return_exceptions=True)
                    pending = set()
                    break
    finally:
        if soft_task is not None:
            soft_task.cancel()
            try:
                await soft_task
            except asyncio.CancelledError:
                pass
        for t in tasks:
            if not t.done():
                t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    if not completed:
        return None

    best_cand, best_quote = min(completed, key=lambda pair: pair[1].price)
    found_ret = (
        best_cand.return_date if best_cand.return_date is not None else best_quote.return_date
    )
    if found_ret is not None and best_quote.return_date != found_ret:
        best_quote = replace(best_quote, return_date=found_ret)

    quotes_only = [q for _, q in completed]
    partial = len(completed) < combinations_count
    band = None
    # Полный поиск: CS-05 band для найденной даты. Partial/soft — samples без лишнего provider.
    if not partial:
        try:
            rem = _remaining_hard()
            if rem is None or rem > 0.4:
                if rem is not None:
                    band = await asyncio.wait_for(
                        provider.get_trip_band(
                            origins,
                            destinations,
                            depart_date=best_cand.depart_date,
                            return_date=best_cand.return_date,
                            adults=adults,
                            children=children,
                            infants=infants,
                            currency=currency,
                        ),
                        timeout=rem,
                    )
                else:
                    band = await provider.get_trip_band(
                        origins,
                        destinations,
                        depart_date=best_cand.depart_date,
                        return_date=best_cand.return_date,
                        adults=adults,
                        children=children,
                        infants=infants,
                        currency=currency,
                    )
                band = align_band_to_quote(band, best_quote)
        except Exception:
            logger.exception(
                "Flexible search band error found_depart=%s",
                best_cand.depart_date,
            )
            band = None
    if band is None:
        band = _band_from_quotes(quotes_only, currency=currency)

    return FlexibleTripResult(
        quote=best_quote,
        found_depart_date=best_cand.depart_date,
        found_return_date=found_ret,
        offset_days=best_cand.offset_days,
        primary_depart_date=depart_date,
        primary_return_date=return_date,
        flexibility_days=flex,
        band=band,
        partial=partial,
        combinations_count=combinations_count,
        completed_count=len(completed),
    )
