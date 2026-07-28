from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flypingavia.api.telegram_auth import validate_webapp_init_data
from flypingavia.config import Settings, get_settings
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services.locations import resolve_place
from flypingavia.services.prices import build_affiliate_url, build_price_provider

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


class ResolveOut(BaseModel):
    code: str
    name: str
    kind: str
    airports: list[str]
    search_codes: list[str]
    label: str


class QuoteOut(BaseModel):
    origin: str
    destination: str
    origin_name: str
    destination_name: str
    price: Optional[float] = None
    price_per_adult: Optional[float] = None
    currency: str = "RUB"
    level: Optional[str] = None
    origin_airport: Optional[str] = None
    destination_airport: Optional[str] = None
    transfers: Optional[int] = None
    airline: Optional[str] = None
    cheap_max: Optional[float] = None
    typical: Optional[float] = None
    expensive_min: Optional[float] = None
    tickets_url: str
    airports_note: Optional[str] = None
    depart_date: Optional[date] = None
    return_date: Optional[date] = None
    adults: int = 1
    children: int = 0
    infants: int = 0
    trip_type: str = "oneway"


class WatchIn(BaseModel):
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    max_price: float
    depart_date: Optional[date] = None
    return_date: Optional[date] = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    infants: int = Field(default=0, ge=0, le=9)


class WatchOut(BaseModel):
    id: int
    origin: str
    destination: str
    origin_name: Optional[str]
    destination_name: Optional[str]
    max_price: float
    depart_date: Optional[date]
    return_date: Optional[date] = None
    adults: int = 1
    children: int = 0
    infants: int = 0
    last_price: Optional[float]
    last_origin_airport: Optional[str] = None
    currency: str
    tickets_url: str
    passengers_label: str = ""
    trip_type: str = "oneway"

def create_api(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    provider = build_price_provider(settings)
    app = FastAPI(title="FlyPingAvia Mini App", version="0.2.0")

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    async def current_user(
        x_telegram_init_data: Annotated[str | None, Header()] = None,
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict:
        init_data = x_telegram_init_data
        if not init_data and authorization and authorization.lower().startswith("tma "):
            init_data = authorization[4:].strip()

        if init_data:
            try:
                return validate_webapp_init_data(init_data, settings.bot_token)
            except ValueError as exc:
                raise HTTPException(status_code=401, detail=str(exc)) from exc

        if settings.webapp_dev_user_id:
            return {
                "user_id": settings.webapp_dev_user_id,
                "username": "dev",
                "user": {"id": settings.webapp_dev_user_id, "username": "dev"},
            }

        raise HTTPException(
            status_code=401,
            detail="Откройте Mini App из Telegram или задайте WEBAPP_DEV_USER_ID для отладки",
        )

    @app.get("/")
    async def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(404, "Mini App UI не собран")
        return FileResponse(index_path)

    @app.get("/api/health")
    async def health() -> dict:
        return {
            "ok": True,
            "demo_prices": settings.is_demo_prices,
            "webapp_url": settings.webapp_url or None,
        }

    @app.get("/api/me")
    async def me(user: dict = Depends(current_user)) -> dict:
        return {"id": user["user_id"], "username": user.get("username"), "user": user.get("user")}

    @app.get("/api/resolve", response_model=list[ResolveOut])
    async def api_resolve(q: str = Query(min_length=1), user: dict = Depends(current_user)) -> list[ResolveOut]:
        _ = user
        place, candidates = await resolve_place(q)
        places = [place] if place else candidates
        return [
            ResolveOut(
                code=p.code,
                name=p.name,
                kind=p.kind,
                airports=list(p.airport_codes),
                search_codes=list(p.search_codes),
                label=p.short_label,
            )
            for p in places[:10]
            if p is not None
        ]

    @app.get("/api/quote", response_model=QuoteOut)
    async def api_quote(
        origin: str,
        destination: str,
        depart_date: Optional[date] = None,
        return_date: Optional[date] = None,
        adults: int = Query(default=1, ge=1, le=9),
        children: int = Query(default=0, ge=0, le=9),
        infants: int = Query(default=0, ge=0, le=9),
        user: dict = Depends(current_user),
    ) -> QuoteOut:
        _ = user
        origin_place, _ = await resolve_place(origin)
        dest_place, _ = await resolve_place(destination)
        if not origin_place or not dest_place:
            raise HTTPException(400, "Не удалось распознать город/аэропорт")
        if return_date and depart_date and return_date < depart_date:
            raise HTTPException(400, "Дата возврата раньше вылета")

        quote = await provider.get_trip_quote(
            origin_place.search_codes,
            dest_place.search_codes,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=settings.currency,
        )
        band = await provider.get_trip_band(
            origin_place.search_codes,
            dest_place.search_codes,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            currency=settings.currency,
        )
        level = band.classify(quote.price).value if quote and band else None
        note = None
        if origin_place.kind == "city" and len(origin_place.airport_codes) > 1:
            note = f"Проверены аэропорты: {', '.join(origin_place.airport_codes)}"

        return QuoteOut(
            origin=origin_place.code,
            destination=dest_place.code,
            origin_name=origin_place.name,
            destination_name=dest_place.name,
            price=quote.price if quote else None,
            price_per_adult=quote.price_per_adult if quote else None,
            currency=(quote.currency if quote else settings.currency.upper()),
            level=level,
            origin_airport=quote.origin_code if quote else None,
            destination_airport=quote.destination_code if quote else None,
            transfers=quote.transfers if quote else None,
            airline=quote.airline if quote else None,
            cheap_max=band.cheap_max if band else None,
            typical=band.typical if band else None,
            expensive_min=band.expensive_min if band else None,
            tickets_url=build_affiliate_url(
                origin_place.code,
                dest_place.code,
                settings.affiliate_marker,
                depart_date,
                return_date=return_date,
                adults=adults,
                children=children,
                infants=infants,
            ),
            airports_note=note,
            depart_date=depart_date,
            return_date=return_date,
            adults=adults,
            children=children,
            infants=infants,
            trip_type="round" if return_date else "oneway",
        )

    def _watch_out(w) -> WatchOut:
        return WatchOut(
            id=w.id,
            origin=w.origin,
            destination=w.destination,
            origin_name=w.origin_name,
            destination_name=w.destination_name,
            max_price=w.max_price,
            depart_date=w.depart_date,
            return_date=w.return_date,
            adults=w.adults or 1,
            children=w.children or 0,
            infants=w.infants or 0,
            last_price=w.last_price,
            last_origin_airport=w.last_origin_airport,
            currency=w.currency,
            tickets_url=build_affiliate_url(
                w.origin,
                w.destination,
                settings.affiliate_marker,
                w.depart_date,
                return_date=w.return_date,
                adults=w.adults or 1,
                children=w.children or 0,
                infants=w.infants or 0,
            ),
            passengers_label=w.passengers_label,
            trip_type="round" if w.return_date else "oneway",
        )

    @app.get("/api/watches", response_model=list[WatchOut])
    async def api_list_watches(user: dict = Depends(current_user)) -> list[WatchOut]:
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user["user_id"], username=user.get("username")
            )
            watches = list(await repo.list_watches(session, db_user.id))
            return [_watch_out(w) for w in watches]

    @app.post("/api/watches", response_model=WatchOut)
    async def api_create_watch(body: WatchIn, user: dict = Depends(current_user)) -> WatchOut:
        origin_place, _ = await resolve_place(body.origin)
        dest_place, _ = await resolve_place(body.destination)
        if not origin_place or not dest_place:
            raise HTTPException(400, "Не удалось распознать маршрут")
        if body.return_date and body.depart_date and body.return_date < body.depart_date:
            raise HTTPException(400, "Дата возврата раньше вылета")
        if body.infants > body.adults:
            raise HTTPException(400, "Младенцев не больше, чем взрослых")

        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user["user_id"], username=user.get("username")
            )
            watch = await repo.add_watch(
                session,
                user=db_user,
                origin=origin_place.code,
                destination=dest_place.code,
                origin_name=origin_place.name,
                destination_name=dest_place.name,
                origin_search=",".join(origin_place.search_codes),
                destination_search=",".join(dest_place.search_codes),
                max_price=body.max_price,
                depart_date=body.depart_date,
                return_date=body.return_date,
                adults=body.adults,
                children=body.children,
                infants=body.infants,
                currency=settings.currency,
            )
            return _watch_out(watch)

    @app.delete("/api/watches/{watch_id}")
    async def api_delete_watch(watch_id: int, user: dict = Depends(current_user)) -> dict:
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user["user_id"], username=user.get("username")
            )
            ok = await repo.deactivate_watch(session, db_user.id, watch_id)
        if not ok:
            raise HTTPException(404, "Подписка не найдена")
        return {"ok": True}

    return app
