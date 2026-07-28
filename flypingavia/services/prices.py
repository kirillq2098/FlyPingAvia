from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import md5
from typing import Optional
from urllib.parse import urlencode

import httpx

from flypingavia.config import Settings


@dataclass(frozen=True)
class PriceQuote:
    price: float
    currency: str
    airline: Optional[str] = None
    transfers: Optional[int] = None
    source: str = "demo"


class PriceProvider:
    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        raise NotImplementedError


class DemoPriceProvider(PriceProvider):
    """Синтетические цены для локальной разработки без API-токена."""

    async def get_cheapest(
        self,
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        currency: str = "rub",
    ) -> Optional[PriceQuote]:
        seed = f"{origin}:{destination}:{depart_date or 'any'}".upper()
        digest = int(md5(seed.encode()).hexdigest()[:8], 16)
        base = 4_000 + (digest % 40_000)
        # Лёгкая «волатильность» по дню, чтобы алерты срабатывали в demo
        day_factor = (date.today().toordinal() + digest) % 7
        price = float(base - day_factor * 350)
        return PriceQuote(
            price=max(price, 1_500.0),
            currency=currency.upper(),
            airline="DP",
            transfers=digest % 3,
            source="demo",
        )


class TravelpayoutsPriceProvider(PriceProvider):
    """Цены через Travelpayouts / Aviasales Data API."""

    CHEAP_URL = "https://api.travelpayouts.com/v1/prices/cheap"
    LATEST_URL = "https://api.travelpayouts.com/v2/prices/latest"

    def __init__(self, token: str, timeout: float = 20.0) -> None:
        self._token = token
        self._timeout = timeout

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
            url = self.CHEAP_URL
        else:
            params["period_type"] = "year"
            params["sorting"] = "price"
            params["one_way"] = "true"
            url = self.LATEST_URL

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()

        if not payload.get("success", True):
            return None

        data = payload.get("data") or {}
        if depart_date is not None:
            # cheap API: { "IST": { "0": { "price": ... } } }
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
            )

        # latest API: list of offers
        if isinstance(data, list) and data:
            offer = data[0]
            return PriceQuote(
                price=float(offer["value"]),
                currency=currency.upper(),
                airline=offer.get("airline"),
                transfers=offer.get("number_of_changes"),
                source="travelpayouts",
            )
        return None


def build_price_provider(settings: Settings) -> PriceProvider:
    if settings.is_demo_prices:
        return DemoPriceProvider()
    return TravelpayoutsPriceProvider(settings.travelpayouts_token)


def build_affiliate_url(
    origin: str,
    destination: str,
    marker: str,
    depart_date: Optional[date] = None,
) -> str:
    """Партнёрская ссылка Aviasales через Travelpayouts marker."""
    params = {
        "origin_iata": origin.upper(),
        "destination_iata": destination.upper(),
        "marker": marker,
        "with_request": "true",
    }
    if depart_date is not None:
        params["depart_date"] = depart_date.isoformat()
    return f"https://www.aviasales.ru/search?{urlencode(params)}"
