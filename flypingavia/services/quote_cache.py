"""Quote / market snapshot cache with stale-while-revalidate + request coalescing."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

FRESH_TTL_SECONDS = 15 * 60  # 15 min
STALE_TTL_SECONDS = 60 * 60  # 60 min


def _iso(d: date | None) -> str:
    return d.isoformat() if d is not None else ""


def make_quote_cache_key(
    *,
    origin: str,
    destination: str,
    origin_search: str,
    destination_search: str,
    depart_date: date | None,
    return_date: date | None,
    flexibility_days: int,
    adults: int,
    children: int,
    infants: int,
    currency: str,
    trip_type: str,
    provider: str,
) -> str:
    payload = {
        "origin": (origin or "").upper(),
        "destination": (destination or "").upper(),
        "origin_search": ",".join(
            sorted(c.strip().upper() for c in (origin_search or "").split(",") if c.strip())
        ),
        "destination_search": ",".join(
            sorted(c.strip().upper() for c in (destination_search or "").split(",") if c.strip())
        ),
        "depart_date": _iso(depart_date),
        "return_date": _iso(return_date),
        "flexibility_days": int(flexibility_days or 0),
        "adults": int(adults or 1),
        "children": int(children or 0),
        "infants": int(infants or 0),
        "currency": (currency or "RUB").upper(),
        "trip_type": (trip_type or "oneway").lower(),
        "provider": (provider or "travelpayouts").lower(),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class QuoteCacheEntry:
    data: dict[str, Any]
    created_at: float  # time.time()
    provider: str = "travelpayouts"

    @property
    def age_seconds(self) -> int:
        return max(0, int(time.time() - self.created_at))

    @property
    def computed_at_iso(self) -> str:
        return datetime.fromtimestamp(self.created_at, tz=timezone.utc).isoformat()


@dataclass
class QuoteMetrics:
    latencies_ms: list[float] = field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
    stale_serves: int = 0
    timeouts: int = 0
    partials: int = 0
    provider_errors: int = 0
    combinations: list[int] = field(default_factory=list)
    live_success: int = 0
    live_timeout: int = 0
    live_error: int = 0
    live_no_results: int = 0
    fallback_used: int = 0

    def record_latency(self, ms: float) -> None:
        self.latencies_ms.append(float(ms))
        if len(self.latencies_ms) > 2000:
            self.latencies_ms = self.latencies_ms[-1000:]

    def percentile(self, pct: float) -> float | None:
        if not self.latencies_ms:
            return None
        vals = sorted(self.latencies_ms)
        idx = int(round((len(vals) - 1) * pct))
        return vals[max(0, min(len(vals) - 1, idx))]

    def snapshot(self) -> dict[str, Any]:
        total = self.cache_hits + self.cache_misses
        hit_rate = (self.cache_hits / total) if total else 0.0
        return {
            "quote_latency_ms_p50": self.percentile(0.50),
            "quote_latency_ms_p95": self.percentile(0.95),
            "quote_cache_hit_rate": round(hit_rate, 4),
            "quote_cache_hits": self.cache_hits,
            "quote_cache_misses": self.cache_misses,
            "quote_stale_serves": self.stale_serves,
            "quote_timeout_count": self.timeouts,
            "quote_partial_result_count": self.partials,
            "quote_provider_error_count": self.provider_errors,
            "live_success": self.live_success,
            "live_timeout": self.live_timeout,
            "live_error": self.live_error,
            "live_no_results": self.live_no_results,
            "fallback_used": self.fallback_used,
            "quote_combinations_count_avg": (
                round(sum(self.combinations) / len(self.combinations), 2)
                if self.combinations
                else None
            ),
            "samples": len(self.latencies_ms),
        }


class QuoteCache:
    def __init__(
        self,
        *,
        fresh_ttl: float = FRESH_TTL_SECONDS,
        stale_ttl: float = STALE_TTL_SECONDS,
        max_entries: int = 256,
    ) -> None:
        self.fresh_ttl = float(fresh_ttl)
        self.stale_ttl = float(stale_ttl)
        self._max = max(32, int(max_entries))
        self._store: dict[str, QuoteCacheEntry] = {}
        self._inflight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self.metrics = QuoteMetrics()

    def clear(self) -> None:
        self._store.clear()
        self._inflight.clear()
        self.metrics = QuoteMetrics()

    def lookup(self, key: str) -> tuple[Optional[QuoteCacheEntry], str]:
        """Return (entry, status) where status is fresh|stale|miss."""
        entry = self._store.get(key)
        if entry is None:
            return None, "miss"
        age = time.time() - entry.created_at
        if age <= self.fresh_ttl:
            return entry, "fresh"
        if age <= self.stale_ttl:
            return entry, "stale"
        self._store.pop(key, None)
        return None, "miss"

    def store(self, key: str, data: dict[str, Any], *, provider: str = "travelpayouts") -> QuoteCacheEntry:
        if len(self._store) >= self._max:
            oldest = sorted(self._store.items(), key=lambda kv: kv[1].created_at)[
                : max(1, self._max // 10)
            ]
            for k, _ in oldest:
                self._store.pop(k, None)
        entry = QuoteCacheEntry(data=data, created_at=time.time(), provider=provider)
        self._store[key] = entry
        return entry

    async def coalesce(
        self,
        key: str,
        factory: Callable[[], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """Single-flight: parallel callers with the same key share one compute."""
        async with self._lock:
            existing = self._inflight.get(key)
            if existing is not None:
                fut: asyncio.Future = existing
            else:
                loop = asyncio.get_running_loop()
                fut = loop.create_future()
                self._inflight[key] = fut

                async def _run() -> None:
                    try:
                        result = await factory()
                        if not fut.done():
                            fut.set_result(result)
                    except Exception as exc:
                        if not fut.done():
                            fut.set_exception(exc)
                    finally:
                        async with self._lock:
                            if self._inflight.get(key) is fut:
                                self._inflight.pop(key, None)

                asyncio.create_task(_run())

        return await asyncio.shield(fut)


# Process-wide cache for Mini App quote endpoint.
default_quote_cache = QuoteCache()
