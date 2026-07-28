from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum
from hashlib import md5
from statistics import median
from typing import Optional, Sequence
from urllib.parse import urlencode

import httpx

from flypingavia.config import Settings


class PriceLevel(str, Enum):
    CHEAP = "cheap"
    NORMAL = "normal"
    EXPENSIVE = "expensive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PriceQuote:
    price: float  # итого за всех пассажиров (и туда-обратно, если выбран RT)
    currency: str
    airline: Optional[str] = None
    transfers: Optional[int] = None
    source: str = "demo"
    origin_code: Optional[str] = None
    destination_code: Optional[str] = None
    searched_origins: tuple[str, ...] = ()
    searched_destinations: tuple[str, ...] = ()
    price_per_adult: Optional[float] = None
    adults: int = 1
    children: int = 0
    infants: int = 0
    return_date: Optional[date] = None
    return_origin_code: Optional[str] = None


def passenger_total(base_per_adult: float, adults: int = 1, children: int = 0, infants: int = 0) -> float:
    """Ориентир суммы: дети ≈ полный тариф, младенцы ≈ 10%."""
    adults = max(1, int(adults))
    children = max(0, int(children))
    infants = max(0, int(infants))
    return float(base_per_adult * adults + base_per_adult * children + base_per_adult * 0.1 * infants)


def scale_band(band: Optional[PriceBand], multiplier: float) -> Optional[PriceBand]:
    if band is None:
        return None
    mult = max(multiplier, 1.0)
    return PriceBand(
        cheap_max=round(band.cheap_max * mult),
        typical=round(band.typical * mult),
        expensive_min=round(band.expensive_min * mult),
        sample_size=band.sample_size,
        currency=band.currency,
        source=band.source,
    )


@dataclass(frozen=True)
class PriceBand:
    """Вилка цен: дёшево / обычно / дорого."""

    cheap_max: float
    typical: float
    expensive_min: float
    sample_size: int
    currency: str = "RUB"
    source: str = "demo"

    def classify(self, price: float) -> PriceLevel:
        if price <= self.cheap_max:
            return PriceLevel.CHEAP
        if price >= self.expensive_min:
            return PriceLevel.EXPENSIVE
        return PriceLevel.NORMAL


def compute_price_band(prices: Sequence[float], currency: str = "RUB", source: str = "api") -> Optional[PriceBand]:
    values = sorted(float(p) for p in prices if p and p > 0)
    if not values:
        return None
    if len(values) == 1:
        p = values[0]
        return PriceBand(
            cheap_max=round(p * 0.9),
            typical=round(p),
            expensive_min=round(p * 1.2),
            sample_size=1,
            currency=currency.upper(),
            source=source,
        )

    n = len(values)

    def percentile(pct: float) -> float:
        idx = int(round((n - 1) * pct))
        return values[max(0, min(n - 1, idx))]

    cheap_max = percentile(0.25)
    typical = float(median(values))
    expensive_min = percentile(0.75)

    # Гарантируем порядок и заметный разброс
    if cheap_max >= typical:
        cheap_max = max(values[0], typical * 0.85)
    if expensive_min <= typical:
        expensive_min = typical * 1.2

    return PriceBand(
        cheap_max=round(cheap_max),
        typical=round(typical),
        expensive_min=round(expensive_min),
        sample_size=n,
        currency=currency.upper(),
        source=source,
    )


class PriceProvider:
    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        raise NotImplementedError

    async def get_price_band(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        raise NotImplementedError

    async def get_cheapest_across(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        """Ищет по всем парам origin×destination и возвращает самый дешёвый вариант."""
        best: Optional[PriceQuote] = None
        origin_list = [c.upper() for c in origins if c]
        dest_list = [c.upper() for c in destinations if c]
        if not origin_list or not dest_list:
            return None

        for origin in origin_list:
            for destination in dest_list:
                try:
                    quote = await self.get_cheapest(origin, destination, depart_date, currency)
                except Exception:
                    continue
                if quote is None:
                    continue
                enriched = PriceQuote(
                    price=quote.price,
                    currency=quote.currency,
                    airline=quote.airline,
                    transfers=quote.transfers,
                    source=quote.source,
                    origin_code=origin,
                    destination_code=destination,
                    searched_origins=tuple(origin_list),
                    searched_destinations=tuple(dest_list),
                )
                if best is None or enriched.price < best.price:
                    best = enriched
        return best

    async def get_price_band_across(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        bands: list[PriceBand] = []
        for origin in origins:
            for destination in destinations:
                try:
                    band = await self.get_price_band(origin, destination, depart_date, currency)
                except Exception:
                    continue
                if band is not None:
                    bands.append(band)
        if not bands:
            return None
        cheap = min(b.cheap_max for b in bands)
        typical = float(median([b.typical for b in bands]))
        expensive = max(b.expensive_min for b in bands)
        if cheap >= typical:
            cheap = typical * 0.85
        if expensive <= typical:
            expensive = typical * 1.2
        return PriceBand(
            cheap_max=round(cheap),
            typical=round(typical),
            expensive_min=round(expensive),
            sample_size=sum(b.sample_size for b in bands),
            currency=bands[0].currency,
            source=bands[0].source,
        )

    async def get_trip_quote(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        *,
        depart_date: Optional[date] = None,
        return_date: Optional[date] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        outbound = await self.get_cheapest_across(origins, destinations, depart_date, currency)
        if outbound is None:
            return None

        per_adult = outbound.price
        return_origin = None
        inbound = None
        if return_date is not None:
            inbound = await self.get_cheapest_across(destinations, origins, return_date, currency)
            if inbound is None:
                # запасной вариант: удвоить one-way как ориентир
                per_adult = outbound.price * 2
            else:
                per_adult = outbound.price + inbound.price
                return_origin = inbound.origin_code

        total = passenger_total(per_adult, adults, children, infants)
        return PriceQuote(
            price=total,
            currency=outbound.currency,
            airline=outbound.airline,
            transfers=outbound.transfers,
            source=outbound.source,
            origin_code=outbound.origin_code,
            destination_code=outbound.destination_code,
            searched_origins=outbound.searched_origins,
            searched_destinations=outbound.searched_destinations,
            price_per_adult=per_adult,
            adults=max(1, adults),
            children=max(0, children),
            infants=max(0, infants),
            return_date=return_date,
            return_origin_code=return_origin,
        )

    async def get_trip_band(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        *,
        depart_date: Optional[date] = None,
        return_date: Optional[date] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        band = await self.get_price_band_across(origins, destinations, depart_date, currency)
        if band is None:
            return None
        # пассажиры
        pax_mult = passenger_total(1.0, adults, children, infants)
        # туда-обратно ≈ ×2 к вилке one-way
        rt_mult = 2.0 if return_date is not None else 1.0
        return scale_band(band, pax_mult * rt_mult)


class DemoPriceProvider(PriceProvider):
    """Синтетические цены для локальной разработки без API-токена."""

    def _base(self, origin: str, destination: str, depart_date: Optional[date]) -> int:
        seed = f"{origin}:{destination}:{depart_date or 'any'}".upper()
        digest = int(md5(seed.encode()).hexdigest()[:8], 16)
        return 4_000 + (digest % 40_000)

    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        base = self._base(origin, destination, depart_date)
        day_factor = (date.today().toordinal() + base) % 7
        price = float(base - day_factor * 350)
        return PriceQuote(
            price=max(price, 1_500.0),
            currency=currency.upper(),
            airline="DP",
            transfers=base % 3,
            source="demo",
            origin_code=origin.upper(),
            destination_code=destination.upper(),
        )

    async def get_price_band(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        base = float(self._base(origin, destination, depart_date))
        samples = [base * f for f in (0.72, 0.85, 0.95, 1.0, 1.1, 1.25, 1.45, 1.7)]
        return compute_price_band(samples, currency=currency, source="demo")


class TravelpayoutsPriceProvider(PriceProvider):
    """Цены через Travelpayouts / Aviasales Data API."""

    CHEAP_URL = "https://api.travelpayouts.com/v1/prices/cheap"
    LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"
    CALENDAR_URL = "https://api.travelpayouts.com/v1/prices/calendar"
    MONTH_MATRIX_URL = "https://api.travelpayouts.com/v2/prices/month-matrix"

    def __init__(self, token: str, timeout: float = 20.0) -> None:
        self._token = token
        self._timeout = timeout

    async def _get_json(self, url: str, params: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        params: dict[str, str] = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "currency": currency.lower(),
            "token": self._token,
            "limit": "1",
        }
        if depart_date is not None:
            params["depart_date"] = depart_date.strftime("%Y-%m")
            payload = await self._get_json(self.CHEAP_URL, params)
            if not payload.get("success", True):
                return None
            data = payload.get("data") or {}
            if not isinstance(data, dict):
                return None
            dest_block = data.get(destination.upper()) or next(iter(data.values()), None)
            if not isinstance(dest_block, dict) or not dest_block:
                return None
            offer = next(iter(dest_block.values()))
            return PriceQuote(
                price=float(offer["price"]),
                currency=currency.upper(),
                airline=offer.get("airline"),
                transfers=offer.get("transfers"),
                source="travelpayouts",
                origin_code=origin.upper(),
                destination_code=destination.upper(),
            )

        params["period_type"] = "year"
        params["sorting"] = "price"
        params["one_way"] = "true"
        payload = await self._get_json(self.LATEST_URL, params)
        data = payload.get("data") or []
        if isinstance(data, list) and data:
            offer = data[0]
            return PriceQuote(
                price=float(offer["value"]),
                currency=currency.upper(),
                airline=offer.get("airline"),
                transfers=offer.get("number_of_changes"),
                source="travelpayouts",
                origin_code=origin.upper(),
                destination_code=destination.upper(),
            )
        return None

    async def _sample_month_matrix(
        self,
        origin: str,
        destination: str,
        currency: str,
        month: Optional[date] = None,
    ) -> list[float]:
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "currency": currency.lower(),
            "token": self._token,
            "show_to_affiliates": "true",
        }
        if month is not None:
            params["month"] = month.strftime("%Y-%m-%d")
        payload = await self._get_json(self.MONTH_MATRIX_URL, params)
        data = payload.get("data") or []
        if not isinstance(data, list):
            return []
        return [float(item["value"]) for item in data if item.get("value")]

    async def _sample_calendar(
        self,
        origin: str,
        destination: str,
        year_month: str,
        currency: str,
    ) -> list[float]:
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "depart_date": year_month,
            "calendar_type": "departure_date",
            "currency": currency.lower(),
            "token": self._token,
        }
        payload = await self._get_json(self.CALENDAR_URL, params)
        if not payload.get("success", True):
            return []
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return []
        prices: list[float] = []
        for item in data.values():
            if not isinstance(item, dict) or not item.get("price"):
                continue
            # Берём только one-way: у туда-обратно обычно заполнен return_at
            if item.get("return_at"):
                continue
            prices.append(float(item["price"]))
        return prices

    async def _sample_latest(
        self,
        origin: str,
        destination: str,
        currency: str,
    ) -> list[float]:
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "currency": currency.lower(),
            "token": self._token,
            "period_type": "year",
            "page": "1",
            "limit": "100",
            "show_to_affiliates": "true",
            "one_way": "true",
        }
        payload = await self._get_json(self.LATEST_URL, params)
        data = payload.get("data") or []
        if not isinstance(data, list):
            return []
        return [float(item["value"]) for item in data if item.get("value")]

    async def get_price_band(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceBand]:
        samples: list[float] = []
        try:
            if depart_date is not None:
                # Календарь часто отдаёт туда-обратно — для one-way берём матрицу месяца
                samples.extend(
                    await self._sample_month_matrix(origin, destination, currency, depart_date)
                )
                one_way_calendar = await self._sample_calendar(
                    origin, destination, depart_date.strftime("%Y-%m"), currency
                )
                samples.extend(one_way_calendar)
            else:
                today = date.today()
                for offset in range(0, 6):
                    month_index = today.month - 1 + offset
                    month = date(today.year + month_index // 12, month_index % 12 + 1, 1)
                    samples.extend(
                        await self._sample_month_matrix(origin, destination, currency, month)
                    )
            samples.extend(await self._sample_latest(origin, destination, currency))
        except Exception:
            if len(samples) < 3:
                quote = await self.get_cheapest(origin, destination, depart_date, currency)
                if quote is None:
                    return None
                samples = [quote.price]
        return compute_price_band(samples, currency=currency, source="travelpayouts")


def build_price_provider(settings: Settings) -> PriceProvider:
    if settings.is_demo_prices:
        return DemoPriceProvider()
    return TravelpayoutsPriceProvider(settings.travelpayouts_token)


def build_affiliate_url(
    origin: str,
    destination: str,
    marker: str,
    depart_date: Optional[date] = None,
    *,
    return_date: Optional[date] = None,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
) -> str:
    """Партнёрская ссылка Aviasales через Travelpayouts marker."""
    params = {
        "origin_iata": origin.upper(),
        "destination_iata": destination.upper(),
        "marker": marker,
        "with_request": "true",
        "adults": str(max(1, adults)),
        "children": str(max(0, children)),
        "infants": str(max(0, infants)),
    }
    if depart_date is not None:
        params["depart_date"] = depart_date.isoformat()
    if return_date is not None:
        params["return_date"] = return_date.isoformat()
        params["one_way"] = "false"
    else:
        params["one_way"] = "true"
    return f"https://www.aviasales.ru/search?{urlencode(params)}"
