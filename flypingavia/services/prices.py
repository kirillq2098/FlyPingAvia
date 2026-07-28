from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum
from hashlib import md5
from statistics import median
from typing import Optional, Sequence
from urllib.parse import urlencode

import httpx

from flypingavia.config import Settings
from flypingavia.services.flight_search import (
    FlightSearchAccessDenied,
    FlightSearchClient,
    FlightSearchError,
)

logger = logging.getLogger(__name__)


class PriceLevel(str, Enum):
    CHEAP = "cheap"
    NORMAL = "normal"
    EXPENSIVE = "expensive"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PriceQuote:
    # live_search: итого за всех пассажиров; иначе обычно за 1 взрослого
    price: float
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

    @property
    def is_live(self) -> bool:
        return self.source == "live_search"

    @property
    def is_total_for_passengers(self) -> bool:
        return self.is_live

def passenger_total(base_per_adult: float, adults: int = 1, children: int = 0, infants: int = 0) -> float:
    """Грубая оценка суммы (Data API не отдаёт реальные цены за состав)."""
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

        # Data API всегда отдаёт цену за 1 взрослого — не умножаем на состав.
        # Пассажиры нужны для ссылки на Aviasales (там живой поиск за всех).
        return PriceQuote(
            price=float(per_adult),
            currency=outbound.currency,
            airline=outbound.airline,
            transfers=outbound.transfers,
            source=outbound.source,
            origin_code=outbound.origin_code,
            destination_code=outbound.destination_code,
            searched_origins=outbound.searched_origins,
            searched_destinations=outbound.searched_destinations,
            price_per_adult=float(per_adult),
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
        _ = (adults, children, infants)  # вилка тоже за 1 взр.
        band = await self.get_price_band_across(origins, destinations, depart_date, currency)
        if band is None:
            return None
        # туда-обратно ≈ ×2 к вилке one-way (оценка суммы двух сегментов)
        rt_mult = 2.0 if return_date is not None else 1.0
        return scale_band(band, rt_mult)


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
    """Цены через Travelpayouts / Aviasales Data API (+ опционально Flight Search)."""

    CHEAP_URL = "https://api.travelpayouts.com/v1/prices/cheap"
    LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"
    CALENDAR_URL = "https://api.travelpayouts.com/v1/prices/calendar"
    MONTH_MATRIX_URL = "https://api.travelpayouts.com/v2/prices/month-matrix"

    def __init__(
        self,
        token: str,
        timeout: float = 20.0,
        *,
        live_client: FlightSearchClient | None = None,
        live_mode: str = "multi",
    ) -> None:
        self._token = token
        self._timeout = timeout
        self._live = live_client
        self._live_mode = (live_mode or "off").strip().lower()

    def _want_live(self, adults: int, children: int, infants: int) -> bool:
        if self._live is None or not self._live.enabled:
            return False
        if self._live_mode in {"always", "on", "1", "true"}:
            return True
        if self._live_mode in {"multi", "multipax", "passengers"}:
            return adults > 1 or children > 0 or infants > 0
        return False

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
        adults = max(1, int(adults))
        children = max(0, int(children))
        infants = max(0, min(int(infants), adults))

        if depart_date is not None and self._want_live(adults, children, infants):
            origin = next((c for c in origins if c), None)
            destination = next((c for c in destinations if c), None)
            if origin and destination and self._live is not None:
                try:
                    live = await self._live.search(
                        origin=origin,
                        destination=destination,
                        depart_date=depart_date,
                        return_date=return_date,
                        adults=adults,
                        children=children,
                        infants=infants,
                        currency=currency,
                    )
                    if live is not None:
                        return PriceQuote(
                            price=float(live.price),
                            currency=live.currency or currency.upper(),
                            airline=live.airline,
                            transfers=live.transfers,
                            source="live_search",
                            origin_code=live.origin_code or origin.upper(),
                            destination_code=live.destination_code or destination.upper(),
                            searched_origins=tuple(c.upper() for c in origins if c),
                            searched_destinations=tuple(c.upper() for c in destinations if c),
                            price_per_adult=live.price_per_person,
                            adults=adults,
                            children=children,
                            infants=infants,
                            return_date=return_date,
                        )
                except FlightSearchAccessDenied as exc:
                    logger.warning("%s", exc)
                except FlightSearchError as exc:
                    logger.warning("Live search failed, fallback to Data API: %s", exc)
                except Exception:
                    logger.exception("Live search unexpected error, fallback to Data API")

        return await super().get_trip_quote(
            origins,
            destinations,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=currency,
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
        # Вилка строится по Data API (за 1 взр.); для live-цены масштабируем снаружи.
        return await super().get_trip_band(
            origins,
            destinations,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=currency,
        )

    async def _get_json(self, url: str, params: dict[str, str]) -> dict:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    def _quote(
        self,
        *,
        price: float,
        currency: str,
        origin: str,
        destination: str,
        airline: Optional[str] = None,
        transfers: Optional[int] = None,
    ) -> PriceQuote:
        return PriceQuote(
            price=float(price),
            currency=currency.upper(),
            airline=airline,
            transfers=transfers,
            source="travelpayouts",
            origin_code=origin.upper(),
            destination_code=destination.upper(),
        )

    async def _month_matrix_items(
        self,
        origin: str,
        destination: str,
        currency: str,
        month: date,
    ) -> list[dict]:
        params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "currency": currency.lower(),
            "token": self._token,
            "show_to_affiliates": "true",
            "month": month.strftime("%Y-%m-%d"),
        }
        payload = await self._get_json(self.MONTH_MATRIX_URL, params)
        data = payload.get("data") or []
        return data if isinstance(data, list) else []

    async def _cheapest_on_date(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        currency: str,
    ) -> Optional[PriceQuote]:
        """One-way на конкретную дату — через month-matrix (ближе к Aviasales)."""
        target = depart_date.isoformat()
        try:
            items = await self._month_matrix_items(origin, destination, currency, depart_date)
        except Exception:
            items = []

        exact: list[dict] = []
        nearby: list[dict] = []
        for item in items:
            if not item.get("value"):
                continue
            # month-matrix one-way: return_date пустой
            if item.get("return_date"):
                continue
            if item.get("actual") is False:
                continue
            dep = str(item.get("depart_date") or "")
            if dep == target:
                exact.append(item)
            elif dep.startswith(depart_date.strftime("%Y-%m")):
                nearby.append(item)

        pool = exact or nearby
        if pool:
            best = min(pool, key=lambda x: float(x["value"]))
            airline = best.get("airline") or None
            gate = best.get("gate") or ""
            if not airline and gate and "Airlines" in str(gate):
                airline = str(gate).replace(" Airlines", "").strip() or None
            return self._quote(
                price=float(best["value"]),
                currency=currency,
                origin=origin,
                destination=destination,
                airline=airline,
                transfers=best.get("number_of_changes"),
            )

        # Календарь: только one-way (без return_at) — иначе там часто «туда-обратно»
        try:
            params = {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "depart_date": depart_date.strftime("%Y-%m"),
                "calendar_type": "departure_date",
                "currency": currency.lower(),
                "token": self._token,
            }
            payload = await self._get_json(self.CALENDAR_URL, params)
            data = payload.get("data") or {}
            if isinstance(data, dict):
                item = data.get(target)
                if isinstance(item, dict) and item.get("price") and not item.get("return_at"):
                    return self._quote(
                        price=float(item["price"]),
                        currency=currency,
                        origin=origin,
                        destination=destination,
                        airline=item.get("airline"),
                        transfers=item.get("transfers"),
                    )
        except Exception:
            pass

        return None

    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        if depart_date is not None:
            quote = await self._cheapest_on_date(origin, destination, depart_date, currency)
            if quote is not None:
                return quote
            # Нет точной даты — берём минимум one-way по month-matrix за месяц
            try:
                items = await self._month_matrix_items(origin, destination, currency, depart_date)
                one_way = [
                    float(i["value"])
                    for i in items
                    if i.get("value") and not i.get("return_date") and i.get("actual") is not False
                ]
                if one_way:
                    return self._quote(
                        price=min(one_way),
                        currency=currency,
                        origin=origin,
                        destination=destination,
                    )
            except Exception:
                pass
            # Не используем /v1/prices/cheap: там часто цена туда-обратно
            # с чужой датой возврата, которой нет в поиске one-way на Aviasales.
            return None

        params: dict[str, str] = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "currency": currency.lower(),
            "token": self._token,
            "limit": "30",
            "period_type": "year",
            "sorting": "price",
            "one_way": "true",
            "show_to_affiliates": "true",
            "page": "1",
        }
        payload = await self._get_json(self.LATEST_URL, params)
        data = payload.get("data") or []
        if isinstance(data, list) and data:
            offer = min(data, key=lambda x: float(x.get("value") or 1e18))
            return self._quote(
                price=float(offer["value"]),
                currency=currency,
                origin=origin,
                destination=destination,
                airline=offer.get("airline"),
                transfers=offer.get("number_of_changes"),
            )
        return None

    async def _sample_month_matrix(
        self,
        origin: str,
        destination: str,
        currency: str,
        month: Optional[date] = None,
    ) -> list[float]:
        if month is None:
            month = date.today()
        try:
            items = await self._month_matrix_items(origin, destination, currency, month)
        except Exception:
            return []
        return [
            float(item["value"])
            for item in items
            if item.get("value") and not item.get("return_date") and item.get("actual") is not False
        ]

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


def align_band_to_quote(band: Optional[PriceBand], quote: Optional[PriceQuote]) -> Optional[PriceBand]:
    """Если цена живая за всех — подтянуть вилку к тому же масштабу."""
    if band is None or quote is None or not quote.is_live:
        return band
    seats = passenger_total(1.0, quote.adults, quote.children, quote.infants)
    if seats <= 1.0:
        return band
    return scale_band(band, seats)


def build_price_provider(settings: Settings) -> PriceProvider:
    if settings.is_demo_prices:
        return DemoPriceProvider()
    live = None
    if settings.live_search_enabled:
        live = FlightSearchClient(
            settings.travelpayouts_token,
            settings.search_marker,
            host=settings.live_search_host or "flypingavia.app",
        )
    return TravelpayoutsPriceProvider(
        settings.travelpayouts_token,
        live_client=live,
        live_mode=settings.live_search_mode,
    )


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
