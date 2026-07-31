from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from datetime import date
from hashlib import md5
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

SEARCH_START_URL = "https://tickets-api.travelpayouts.com/search/affiliate/start"


class FlightSearchAccessDenied(RuntimeError):
    """Аккаунту не выдан доступ к Flight Search API."""


class FlightSearchError(RuntimeError):
    pass


def _collect_values(obj: Any) -> list[str]:
    values: list[str] = []
    if isinstance(obj, dict):
        for key in sorted(obj.keys()):
            val = obj[key]
            if isinstance(val, (dict, list)):
                values.extend(_collect_values(val))
            else:
                values.append(str(val))
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                values.extend(_collect_values(item))
            else:
                values.append(str(item))
    return values


def make_signature(token: str, params: dict) -> str:
    """MD5(token:values) — values рекурсивно, ключи dict по алфавиту."""
    raw = token + ":" + ":".join(_collect_values(params))
    return md5(raw.encode()).hexdigest()


@dataclass(frozen=True)
class LiveTicketQuote:
    price: float  # итого за всех пассажиров
    currency: str
    airline: Optional[str] = None
    transfers: Optional[int] = None
    origin_code: Optional[str] = None
    destination_code: Optional[str] = None
    price_per_person: Optional[float] = None
    agent: Optional[str] = None


@dataclass
class _CacheEntry:
    quote: LiveTicketQuote
    expires_at: float


class FlightSearchClient:
    """Живой поиск Aviasales через Travelpayouts Flight Search API."""

    def __init__(
        self,
        token: str,
        marker: str,
        *,
        host: str = "flypingavia.app",
        user_ip: str = "127.0.0.1",
        timeout: float = 45.0,
        poll_interval: float = 2.0,
        max_polls: int = 12,
        cache_ttl_seconds: float = 300.0,
    ) -> None:
        self._token = token.strip()
        self._marker = str(marker).strip()
        self._host = host
        self._user_ip = user_ip
        self._timeout = timeout
        self._poll_interval = poll_interval
        self._max_polls = max_polls
        self._cache_ttl = cache_ttl_seconds
        self._cache: dict[str, _CacheEntry] = {}
        self._access_denied = False
        self._access_checked = False

    @property
    def enabled(self) -> bool:
        return bool(self._token and self._marker) and not self._access_denied

    @property
    def access_denied(self) -> bool:
        return self._access_denied

    def _headers(self, signature: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-real-host": self._host,
            "x-user-ip": self._user_ip,
            "x-signature": signature,
            "x-affiliate-user-id": self._token,
        }

    def _cache_key(
        self,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: Optional[date],
        adults: int,
        children: int,
        infants: int,
        currency: str,
    ) -> str:
        ret = return_date.isoformat() if return_date else "-"
        return (
            f"{origin}:{destination}:{depart_date.isoformat()}:{ret}:"
            f"{adults}:{children}:{infants}:{currency.lower()}"
        )

    async def _post(self, url: str, body: dict) -> tuple[int, dict | None, str]:
        payload = {k: v for k, v in body.items() if k != "signature"}
        signature = make_signature(self._token, payload)
        body = dict(body)
        body["signature"] = signature
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=body, headers=self._headers(signature))
        text = response.text
        data = None
        if response.status_code != 304:
            try:
                data = response.json()
            except Exception:
                data = None
        return response.status_code, data, text

    async def probe_access(self) -> str:
        """ok | denied | error — однократная проверка доступа."""
        if self._access_denied:
            return "denied"
        if not self._token or not self._marker:
            return "disabled"
        try:
            status, data, text = await self._start(
                origin="MOW",
                destination="LED",
                depart_date=date.today().replace(day=min(28, date.today().day)),
                return_date=None,
                adults=1,
                children=0,
                infants=0,
                currency="rub",
            )
        except Exception as exc:
            logger.warning("Flight Search probe failed: %s", exc)
            return "error"
        if status == 403 or (isinstance(text, str) and "access denied" in text.lower()):
            self._access_denied = True
            return "denied"
        if status in (200, 201) and isinstance(data, dict) and data.get("search_id"):
            self._access_checked = True
            return "ok"
        return "error"

    async def _start(
        self,
        *,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: Optional[date],
        adults: int,
        children: int,
        infants: int,
        currency: str,
    ) -> tuple[int, dict | None, str]:
        directions = [
            {
                "origin": origin.upper(),
                "destination": destination.upper(),
                "date": depart_date.isoformat(),
            }
        ]
        if return_date is not None:
            directions.append(
                {
                    "origin": destination.upper(),
                    "destination": origin.upper(),
                    "date": return_date.isoformat(),
                }
            )
        body = {
            "marker": self._marker,
            "locale": "ru",
            "currency_code": currency.upper(),
            "market_code": "ru",
            "search_params": {
                "trip_class": "Y",
                "passengers": {
                    "adults": max(1, adults),
                    "children": max(0, children),
                    "infants": max(0, infants),
                },
                "directions": directions,
            },
        }
        return await self._post(SEARCH_START_URL, body)

    async def search(
        self,
        *,
        origin: str,
        destination: str,
        depart_date: date,
        return_date: Optional[date] = None,
        adults: int = 1,
        children: int = 0,
        infants: int = 0,
        currency: str = "rub",
    ) -> Optional[LiveTicketQuote]:
        if not self.enabled:
            return None

        key = self._cache_key(
            origin, destination, depart_date, return_date, adults, children, infants, currency
        )
        cached = self._cache.get(key)
        if cached and cached.expires_at > time.monotonic():
            return cached.quote

        status, data, text = await self._start(
            origin=origin,
            destination=destination,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=currency,
        )
        if status == 403 or "access denied" in (text or "").lower():
            self._access_denied = True
            raise FlightSearchAccessDenied(
                "Нет доступа к Flight Search API. "
                "Напишите в support@travelpayouts.com и укажите числовой marker партнёра."
            )
        if status not in (200, 201) or not isinstance(data, dict):
            raise FlightSearchError(f"start failed: HTTP {status} {text[:200]}")

        search_id = data.get("search_id")
        results_url = (data.get("results_url") or "https://tickets-api.travelpayouts.com").rstrip(
            "/"
        )
        if not search_id:
            raise FlightSearchError(f"no search_id in response: {data}")

        quote = await self._poll_cheapest(results_url, str(search_id), currency.upper())
        if quote is not None:
            self._cache[key] = _CacheEntry(quote=quote, expires_at=time.monotonic() + self._cache_ttl)
        return quote

    async def _poll_cheapest(
        self,
        results_url: str,
        search_id: str,
        currency: str,
    ) -> Optional[LiveTicketQuote]:
        last_ts = 0
        best: Optional[LiveTicketQuote] = None
        agents: dict[Any, dict] = {}

        for _ in range(self._max_polls):
            body = {"search_id": search_id, "last_update_timestamp": last_ts}
            status, data, _text = await self._post(f"{results_url}/search/affiliate/results", body)
            if status == 304:
                await asyncio.sleep(self._poll_interval)
                continue
            if status not in (200, 201) or not isinstance(data, dict):
                await asyncio.sleep(self._poll_interval)
                continue

            for ag in data.get("agents") or []:
                if isinstance(ag, dict) and "id" in ag:
                    agents[ag["id"]] = ag

            for ticket in data.get("tickets") or []:
                q = self._ticket_to_quote(ticket, agents, currency)
                if q is None:
                    continue
                if best is None or q.price < best.price:
                    best = q

            last_ts = int(data.get("last_update_timestamp") or last_ts)
            if data.get("is_over"):
                break
            await asyncio.sleep(self._poll_interval)

        return best

    def _ticket_to_quote(
        self,
        ticket: dict,
        agents: dict[Any, dict],
        currency: str,
    ) -> Optional[LiveTicketQuote]:
        proposals = ticket.get("proposals") or []
        if not proposals:
            return None

        def _amount(p: dict) -> float:
            price = p.get("price") or {}
            try:
                return float(price.get("amount"))
            except (TypeError, ValueError):
                return float("inf")

        best = min(proposals, key=_amount)
        amount = _amount(best)
        if amount == float("inf"):
            return None

        price_info = best.get("price") or {}
        cur = str(price_info.get("currency") or currency).upper()
        ppp = best.get("price_per_person") or {}
        per_person = None
        try:
            if ppp.get("amount") is not None:
                per_person = float(ppp["amount"])
        except (TypeError, ValueError):
            per_person = None

        transfers = None
        segments = ticket.get("segments") or []
        if segments:
            # число пересадок ≈ кол-во flights - 1 на первом сегменте
            flights = (segments[0] or {}).get("flights") or []
            if isinstance(flights, list) and flights:
                transfers = max(0, len(flights) - 1)

        airline = None
        terms = best.get("flight_terms") or []
        if terms and isinstance(terms[0], list) and terms[0]:
            airline = (terms[0][0] or {}).get("carrier")
        elif terms and isinstance(terms[0], dict):
            airline = terms[0].get("carrier")

        agent_id = best.get("agent_id")
        agent_name = None
        if agent_id in agents:
            agent_name = agents[agent_id].get("label") or agents[agent_id].get("name")

        origin_code = None
        destination_code = None
        # иногда есть в ticket
        if segments:
            # без flight_legs сложно — оставим None, подставит вызывающий код
            pass

        return LiveTicketQuote(
            price=float(amount),
            currency=cur,
            airline=airline,
            transfers=transfers,
            origin_code=origin_code,
            destination_code=destination_code,
            price_per_person=per_person,
            agent=agent_name,
        )
