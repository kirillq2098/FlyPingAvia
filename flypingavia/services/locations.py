from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

CITIES_URL = "https://api.travelpayouts.com/data/ru/cities.json"
AIRPORTS_URL = "https://api.travelpayouts.com/data/ru/airports.json"

# Частые разговорные названия → IATA города
ALIASES: dict[str, str] = {
    "мск": "MOW",
    "москва": "MOW",
    "moscow": "MOW",
    "спб": "LED",
    "питер": "LED",
    "петербург": "LED",
    "санктпетербург": "LED",
    "санкт-петербург": "LED",
    "ленинград": "LED",
    "екб": "SVX",
    "екатеринбург": "SVX",
    "нск": "OVB",
    "новосибирск": "OVB",
    "сочи": "AER",
    "адлер": "AER",
    "крым": "SIP",
    "симферополь": "SIP",
    "калининград": "KGD",
    "казань": "KZN",
    "самара": "KUF",
    "нижний": "GOJ",
    "нижнийновгород": "GOJ",
    "ростов": "ROV",
    "ростовнадон": "ROV",
    "краснодар": "KRR",
    "уфа": "UFA",
    "пермь": "PEE",
    "воронеж": "VOZ",
    "минск": "MSQ",
    "киев": "IEV",
    "алматы": "ALA",
    "астана": "NQZ",
    "ташкент": "TAS",
    "баку": "GYD",
    "ереван": "EVN",
    "тбилиси": "TBS",
    "стамбул": "IST",
    "анталья": "AYT",
    "анталия": "AYT",
    "дубай": "DXB",
    "шарм": "SSH",
    "шармэльшейх": "SSH",
    "хургада": "HRG",
    "париж": "PAR",
    "лондон": "LON",
    "рим": "ROM",
    "милан": "MIL",
    "ньюйорк": "NYC",
    "бангкок": "BKK",
    "пхукет": "HKT",
}


def _norm(text: str) -> str:
    value = text.strip().lower().replace("ё", "е")
    value = value.replace("г.", " ").replace("город", " ")
    value = re.sub(r"[^a-zа-я0-9\-]+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace(" ", "").replace("-", "")
    return value


@dataclass(frozen=True)
class AirportInfo:
    code: str
    name: str
    city_code: str
    flightable: bool = True


@dataclass(frozen=True)
class Place:
    """Город или аэропорт для поиска."""

    code: str  # код для хранения/основного поиска (город предпочтительнее)
    name: str
    kind: str  # city | airport
    country_code: str = ""
    airport_codes: tuple[str, ...] = field(default_factory=tuple)
    airport_names: tuple[str, ...] = field(default_factory=tuple)

    @property
    def search_codes(self) -> tuple[str, ...]:
        """Коды, по которым ищем цену: город + все аэропорты (уникально)."""
        codes: list[str] = [self.code]
        for code in self.airport_codes:
            if code not in codes:
                codes.append(code)
        return tuple(codes)

    @property
    def label(self) -> str:
        if self.kind == "city" and len(self.airport_codes) > 1:
            return f"{self.name} ({self.code}, {len(self.airport_codes)} а/п)"
        if self.kind == "airport":
            return f"{self.name} ({self.code})"
        return f"{self.name} ({self.code})"

    @property
    def short_label(self) -> str:
        return f"{self.name} ({self.code})"


class LocationDirectory:
    def __init__(self) -> None:
        self._cities_by_code: dict[str, dict] = {}
        self._airports_by_code: dict[str, AirportInfo] = {}
        self._airports_by_city: dict[str, list[AirportInfo]] = {}
        self._name_index: dict[str, list[str]] = {}
        self._loaded = False

    async def ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with httpx.AsyncClient(timeout=60.0) as client:
            cities_resp = await client.get(CITIES_URL)
            airports_resp = await client.get(AIRPORTS_URL)
            cities_resp.raise_for_status()
            airports_resp.raise_for_status()
            cities = cities_resp.json()
            airports = airports_resp.json()

        for city in cities:
            code = (city.get("code") or "").upper()
            if not code:
                continue
            if not city.get("has_flightable_airport", True):
                # оставляем в индексе коды, но поиск по имени — только с аэропортами
                pass
            self._cities_by_code[code] = city
            names = {
                city.get("name") or "",
                (city.get("name_translations") or {}).get("en") or "",
                *((city.get("cases") or {}).values() if isinstance(city.get("cases"), dict) else ()),
            }
            for name in names:
                key = _norm(str(name))
                if key:
                    self._name_index.setdefault(key, [])
                    if code not in self._name_index[key]:
                        self._name_index[key].append(code)

        for raw in airports:
            code = (raw.get("code") or "").upper()
            city_code = (raw.get("city_code") or "").upper()
            if not code or not city_code:
                continue
            iata_type = (raw.get("iata_type") or "airport").lower()
            flightable = bool(raw.get("flightable", True))
            # Только лётные аэропорты (без вокзалов и неактивных)
            if iata_type != "airport" or not flightable:
                continue
            info = AirportInfo(
                code=code,
                name=raw.get("name") or (raw.get("name_translations") or {}).get("en") or code,
                city_code=city_code,
                flightable=True,
            )
            self._airports_by_code[code] = info
            self._airports_by_city.setdefault(city_code, []).append(info)
            for name in (info.name, (raw.get("name_translations") or {}).get("en") or ""):
                key = _norm(str(name))
                if key:
                    self._name_index.setdefault(key, [])
                    if code not in self._name_index[key]:
                        self._name_index[key].append(code)

        for alias, code in ALIASES.items():
            self._name_index.setdefault(_norm(alias), [])
            if code not in self._name_index[_norm(alias)]:
                self._name_index[_norm(alias)].insert(0, code)

        self._loaded = True
        logger.info(
            "LocationDirectory loaded: %s cities, %s airports",
            len(self._cities_by_code),
            len(self._airports_by_code),
        )

    def _place_from_code(self, code: str) -> Optional[Place]:
        code = code.upper()
        if code in self._cities_by_code:
            city = self._cities_by_code[code]
            airports = [a for a in self._airports_by_city.get(code, []) if a.flightable]
            # если у города flightable-аэропортов нет, но код города есть — всё равно используем
            if not airports and not city.get("has_flightable_airport", False):
                # возможно это код совпадает с аэропортом
                if code in self._airports_by_code:
                    return self._place_from_airport(code)
            return Place(
                code=code,
                name=city.get("name") or code,
                kind="city",
                country_code=city.get("country_code") or "",
                airport_codes=tuple(a.code for a in airports),
                airport_names=tuple(a.name for a in airports),
            )
        if code in self._airports_by_code:
            return self._place_from_airport(code)
        return None

    def _place_from_airport(self, code: str) -> Place:
        info = self._airports_by_code[code]
        city = self._cities_by_code.get(info.city_code)
        city_name = (city or {}).get("name") or info.city_code
        return Place(
            code=code,
            name=f"{info.name}, {city_name}",
            kind="airport",
            country_code=(city or {}).get("country_code") or "",
            airport_codes=(code,),
            airport_names=(info.name,),
        )

    def resolve_all(self, text: str) -> list[Place]:
        """Вернуть все подходящие места по тексту пользователя."""
        raw = (text or "").strip()
        if not raw:
            return []

        # Прямой IATA
        if re.fullmatch(r"[A-Za-z]{3}", raw):
            place = self._place_from_code(raw.upper())
            return [place] if place else []

        key = _norm(raw)
        if not key:
            return []

        codes = list(self._name_index.get(key, []))

        # частичное совпадение, если точного нет
        if not codes and len(key) >= 3:
            partial: list[str] = []
            for name_key, code_list in self._name_index.items():
                if name_key.startswith(key) or key in name_key:
                    for code in code_list:
                        if code not in partial:
                            partial.append(code)
            codes = partial[:12]

        places: list[Place] = []
        seen: set[str] = set()
        for code in codes:
            place = self._place_from_code(code)
            if place is None:
                continue
            # предпочитаем городской код, если есть
            marker = f"{place.kind}:{place.code}"
            if marker in seen:
                continue
            seen.add(marker)
            # отфильтруем города без аэропортов
            if place.kind == "city" and not place.airport_codes and place.code not in self._airports_by_code:
                city = self._cities_by_code.get(place.code) or {}
                if not city.get("has_flightable_airport"):
                    continue
            places.append(place)
        return places

    def resolve_one(self, text: str) -> tuple[Optional[Place], list[Place]]:
        """
        (единственное место или None, список кандидатов).
        Если кандидат один — он же в first.
        """
        places = self.resolve_all(text)
        if len(places) == 1:
            return places[0], places
        if not places:
            return None, []
        # если среди кандидатов есть точный город по алиасу — берём его
        key = _norm(text)
        alias_code = ALIASES.get(key)
        if alias_code:
            for place in places:
                if place.code == alias_code:
                    return place, places
        return None, places


_directory: LocationDirectory | None = None


def get_location_directory() -> LocationDirectory:
    global _directory
    if _directory is None:
        _directory = LocationDirectory()
    return _directory


async def resolve_place(text: str) -> tuple[Optional[Place], list[Place]]:
    directory = get_location_directory()
    await directory.ensure_loaded()
    return directory.resolve_one(text)
