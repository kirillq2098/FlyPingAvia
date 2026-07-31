"""CS-05: предупреждение о пороге заметно ниже рынка."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

from flypingavia.services.prices import PriceBand


@dataclass(frozen=True)
class LowThresholdDecision:
    warn: bool
    threshold: float
    cheap_max: Optional[float] = None
    typical: Optional[float] = None
    currency: str = "RUB"
    sample_size: int = 0

    @property
    def code(self) -> str | None:
        return "LOW_THRESHOLD_CONFIRMATION_REQUIRED" if self.warn else None


def band_is_usable(band: PriceBand | None) -> bool:
    if band is None:
        return False
    if band.sample_size < 1:
        return False
    if not math.isfinite(band.cheap_max) or not math.isfinite(band.typical):
        return False
    if band.cheap_max <= 0 or band.typical <= 0:
        return False
    if hasattr(band, "expensive_min") and (
        not math.isfinite(band.expensive_min) or band.expensive_min <= 0
    ):
        return False
    return True


def should_warn_low_threshold(
    threshold: float,
    band: PriceBand | None,
) -> bool:
    """True, если порог строго ниже нижней границы дешёвой зоны (cheap_max)."""
    if not math.isfinite(threshold) or threshold <= 0:
        return False
    if not band_is_usable(band):
        return False
    assert band is not None
    return float(threshold) < float(band.cheap_max)


def evaluate_low_threshold(
    threshold: float,
    band: PriceBand | None,
    *,
    currency: str = "RUB",
) -> LowThresholdDecision:
    warn = should_warn_low_threshold(threshold, band)
    if not warn or not band_is_usable(band):
        return LowThresholdDecision(
            warn=False,
            threshold=float(threshold),
            currency=(currency or "RUB").upper(),
        )
    assert band is not None
    return LowThresholdDecision(
        warn=True,
        threshold=float(threshold),
        cheap_max=float(band.cheap_max),
        typical=float(band.typical),
        currency=(band.currency or currency or "RUB").upper(),
        sample_size=int(band.sample_size),
    )


def band_from_snapshot(
    *,
    cheap_max: float | None,
    typical: float | None,
    expensive_min: float | None = None,
    sample_size: int | None = None,
    currency: str = "RUB",
) -> Optional[PriceBand]:
    """Собрать PriceBand из простых FSM/JSON полей (без ORM)."""
    if cheap_max is None or typical is None:
        return None
    if sample_size is None:
        sample_size = 1
    exp = expensive_min if expensive_min is not None else max(float(typical) * 1.2, float(cheap_max) + 1)
    return PriceBand(
        cheap_max=float(cheap_max),
        typical=float(typical),
        expensive_min=float(exp),
        sample_size=int(sample_size),
        currency=(currency or "RUB").upper(),
        source="snapshot",
    )
