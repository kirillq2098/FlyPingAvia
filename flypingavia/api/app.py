from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flypingavia.api.telegram_auth import (
    TelegramAuthError,
    TelegramWebAppUser,
    validate_telegram_init_data,
)
from flypingavia.config import Settings, get_settings
from flypingavia.version import __version__
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services.locations import resolve_place
from flypingavia.services.prices import build_affiliate_url, build_price_provider
from flypingavia.services.flexible_dates import search_flexible_trip, validate_flexibility_days
from flypingavia.services.threshold_policy import evaluate_low_threshold
from flypingavia.bot.formatters import money as format_money

logger = logging.getLogger(__name__)

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
    price_for: str = "adult"  # adult | passengers
    source: Optional[str] = None
    # CS-07 MVP flexible window metadata
    flexibility_days: int = 0
    primary_depart_date: Optional[date] = None
    primary_return_date: Optional[date] = None
    found_depart_date: Optional[date] = None
    found_return_date: Optional[date] = None
    offset_days: int = 0


class WatchIn(BaseModel):
    origin: str = Field(min_length=2)
    destination: str = Field(min_length=2)
    max_price: float
    depart_date: Optional[date] = None
    return_date: Optional[date] = None
    adults: int = Field(default=1, ge=1, le=9)
    children: int = Field(default=0, ge=0, le=9)
    infants: int = Field(default=0, ge=0, le=9)
    confirm_low_threshold: bool = False
    flexibility_days: int = 0


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
    flexibility_days: int = 0
    last_price: Optional[float]
    last_origin_airport: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    currency: str
    tickets_url: str
    passengers_label: str = ""
    trip_type: str = "oneway"

def create_api(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    provider = build_price_provider(settings)
    app = FastAPI(title="FlyPingAvia Mini App", version=__version__)

    if STATIC_DIR.exists():
        app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")

    async def get_current_telegram_user(
        authorization: Annotated[str | None, Header()] = None,
        x_telegram_init_data: Annotated[str | None, Header()] = None,
    ) -> TelegramWebAppUser:
        """Единая dependency: только проверенный initData (или dev user вне production)."""
        init_data = None
        if authorization and authorization.lower().startswith("tma "):
            init_data = authorization[4:].strip()
        elif x_telegram_init_data:
            # Legacy header — принимаем, если уже используется клиентом.
            init_data = x_telegram_init_data.strip()

        if init_data:
            try:
                user = validate_telegram_init_data(
                    init_data,
                    bot_token=settings.bot_token,
                    max_age_seconds=settings.telegram_init_data_max_age_seconds,
                )
            except TelegramAuthError as exc:
                logger.info("Telegram Mini App auth rejected: %s", exc.code)
                raise HTTPException(status_code=401, detail=exc.as_detail()) from exc
            logger.debug("Telegram Mini App auth ok user_id=%s", user.id)
            return user

        # Без initData: только development/test + WEBAPP_DEV_USER_ID > 0
        if settings.is_production:
            raise HTTPException(
                status_code=401,
                detail={
                    "code": "MISSING_INIT_DATA",
                    "message": (
                        "Откройте приложение через Telegram. "
                        "Без данных Telegram доступ запрещён."
                    ),
                },
            )

        dev_id = int(settings.webapp_dev_user_id or 0)
        if dev_id > 0:
            return TelegramWebAppUser(
                id=dev_id,
                first_name="Dev",
                username="dev",
            )

        raise HTTPException(
            status_code=401,
            detail={
                "code": "MISSING_INIT_DATA",
                "message": (
                    "Откройте Mini App из Telegram или задайте "
                    "WEBAPP_DEV_USER_ID для локальной отладки."
                ),
            },
        )

    # Alias for older Depends(current_user) style in this module.
    current_user = get_current_telegram_user

    @app.get("/")
    async def index() -> FileResponse:
        index_path = STATIC_DIR / "index.html"
        if not index_path.exists():
            raise HTTPException(404, "Mini App UI не собран")
        return FileResponse(index_path)

    @app.get("/api/health")
    async def health() -> dict:
        live_status = "disabled"
        if settings.live_search_enabled:
            live = getattr(provider, "_live", None)
            if live is None:
                live_status = "disabled"
            elif live.access_denied:
                live_status = "denied"
            else:
                live_status = "configured"
        issues = settings.readiness_issues()
        bot_link = None
        if settings.telegram_bot_username:
            bot_link = f"https://t.me/{settings.telegram_bot_username}"
        return {
            "status": "ok",
            "ok": True,
            "version": __version__,
            "ready": len(issues) == 0,
            "issues": issues,
            "app_env": settings.app_env,
            "webapp_configured": settings.webapp_configured,
            "webapp_url": settings.webapp_origin,
            "webapp_https": settings.webapp_https,
            "display_timezone": settings.display_timezone,
            "demo_prices": settings.is_demo_prices,
            "live_search_mode": settings.live_search_mode,
            "live_search": live_status,
            "telegram_webapp_auth": True,
            "telegram_bot_username": settings.telegram_bot_username or None,
            "telegram_bot_link": bot_link,
        }

    @app.get("/api/ready")
    async def ready():
        """Readiness относительно APP_ENV.

        development/test: обычно ready=true (без требования публичного HTTPS).
        production: строгие prerequisites (HTTPS WEBAPP_URL, live prices, …).
        HTTP 503 только когда не готово — процесс при этом жив (см. /api/health).
        """
        from fastapi.responses import JSONResponse

        from flypingavia.db.session import session_scope
        from flypingavia.monitoring.health_alerts import count_open_incidents

        issues = settings.readiness_issues()
        open_incidents = 0
        try:
            async with session_scope() as session:
                open_incidents = await count_open_incidents(session)
        except Exception:
            open_incidents = -1

        if open_incidents < 0:
            monitor = {"status": "unknown", "open_incidents": 0}
        elif open_incidents > 0:
            monitor = {"status": "degraded", "open_incidents": open_incidents}
        else:
            monitor = {"status": "ok", "open_incidents": 0}

        payload = {
            "ready": len(issues) == 0,
            "issues": issues,
            "app_env": settings.app_env,
            "health_monitor": monitor,
        }
        if issues:
            return JSONResponse(status_code=503, content=payload)
        return JSONResponse(status_code=200, content=payload)

    @app.get("/api/me")
    async def me(user: TelegramWebAppUser = Depends(current_user)) -> dict:
        # Первый валидный запуск Mini App — создать/обновить User (username).
        async with session_scope() as session:
            await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
        return {
            "telegram_user_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
        }

    @app.get("/api/resolve", response_model=list[ResolveOut])
    async def api_resolve(
        q: str = Query(min_length=1),
        user: TelegramWebAppUser = Depends(current_user),
    ) -> list[ResolveOut]:
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
        flexibility_days: int = Query(default=0),
        user: TelegramWebAppUser = Depends(current_user),
    ) -> QuoteOut:
        _ = user
        origin_place, _ = await resolve_place(origin)
        dest_place, _ = await resolve_place(destination)
        if not origin_place or not dest_place:
            raise HTTPException(400, "Не удалось распознать город/аэропорт")
        if return_date and depart_date and return_date < depart_date:
            raise HTTPException(400, "Дата возврата раньше вылета")
        try:
            flex = validate_flexibility_days(flexibility_days)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        result = await search_flexible_trip(
            provider,
            origins=origin_place.search_codes,
            destinations=dest_place.search_codes,
            depart_date=depart_date,
            return_date=return_date,
            flexibility_days=flex,
            adults=adults,
            children=children,
            infants=infants,
            currency=settings.currency,
        )
        quote = result.quote if result else None
        band = result.band if result else None
        found_dep = result.found_depart_date if result else depart_date
        found_ret = result.found_return_date if result else return_date
        offset = result.offset_days if result else 0

        level = band.classify(quote.price).value if quote and band else None
        note = None
        if origin_place.kind == "city" and len(origin_place.airport_codes) > 1:
            note = f"Проверены аэропорты: {', '.join(origin_place.airport_codes)}"
        if quote and not quote.is_live and (adults > 1 or children or infants):
            extra = "Живой поиск за состав недоступен — цена за 1 взр."
            note = f"{note}. {extra}" if note else extra

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
                found_dep if found_dep is not None else depart_date,
                return_date=found_ret if found_ret is not None else return_date,
                adults=adults,
                children=children,
                infants=infants,
            ),
            airports_note=note,
            depart_date=found_dep if found_dep is not None else depart_date,
            return_date=found_ret if found_ret is not None else return_date,
            adults=adults,
            children=children,
            infants=infants,
            trip_type="round" if return_date else "oneway",
            price_for="passengers" if (quote and quote.is_live) else "adult",
            source=quote.source if quote else None,
            flexibility_days=flex,
            primary_depart_date=depart_date,
            primary_return_date=return_date,
            found_depart_date=found_dep,
            found_return_date=found_ret,
            offset_days=offset,
        )

    def _watch_out(w) -> WatchOut:
        checked = getattr(w, "last_checked_at", None)
        if checked is not None and checked.tzinfo is None:
            checked = checked.replace(tzinfo=timezone.utc)
        elif checked is not None:
            checked = checked.astimezone(timezone.utc)
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
            flexibility_days=int(getattr(w, "flexibility_days", 0) or 0),
            last_price=w.last_price,
            last_origin_airport=w.last_origin_airport,
            last_checked_at=checked,
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
    async def api_list_watches(
        user: TelegramWebAppUser = Depends(current_user),
    ) -> list[WatchOut]:
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            watches = list(await repo.list_watches(session, db_user.id))
            return [_watch_out(w) for w in watches]

    @app.post("/api/watches", response_model=WatchOut)
    async def api_create_watch(
        body: WatchIn,
        user: TelegramWebAppUser = Depends(current_user),
    ) -> WatchOut:
        import math

        origin_place, _ = await resolve_place(body.origin)
        dest_place, _ = await resolve_place(body.destination)
        if not origin_place or not dest_place:
            raise HTTPException(400, "Не удалось распознать маршрут")
        if body.return_date and body.depart_date and body.return_date < body.depart_date:
            raise HTTPException(400, "Дата возврата раньше вылета")
        if body.infants > body.adults:
            raise HTTPException(400, "Младенцев не больше, чем взрослых")
        if not math.isfinite(body.max_price) or body.max_price <= 0:
            raise HTTPException(400, "Порог должен быть положительным числом")
        try:
            flex = validate_flexibility_days(body.flexibility_days)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

        # CS-05: band через тот же flexible search, что и /api/quote.
        band = None
        try:
            result = await search_flexible_trip(
                provider,
                origins=origin_place.search_codes,
                destinations=dest_place.search_codes,
                depart_date=body.depart_date,
                return_date=body.return_date,
                flexibility_days=flex,
                adults=body.adults,
                children=body.children,
                infants=body.infants,
                currency=settings.currency,
            )
            if result is not None:
                band = result.band
        except Exception:
            logger.exception(
                "Failed to evaluate flexible market band before Watch creation"
            )
            band = None

        decision = evaluate_low_threshold(
            body.max_price,
            band,
            currency=settings.currency,
        )
        if decision.warn and not body.confirm_low_threshold:
            cheap = decision.cheap_max or 0
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "LOW_THRESHOLD_CONFIRMATION_REQUIRED",
                    "threshold": decision.threshold,
                    "cheap_max": decision.cheap_max,
                    "typical": decision.typical,
                    "currency": decision.currency,
                    "message": (
                        "Порог заметно ниже текущего рынка. "
                        f"Вы выбрали {format_money(decision.threshold, decision.currency)}, "
                        f"дешёвая зона до {format_money(cheap, decision.currency)}. "
                        "С таким порогом уведомление может долго не прийти."
                    ),
                },
            )

        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
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
                flexibility_days=flex,
            )
            return _watch_out(watch)

    @app.delete("/api/watches/{watch_id}")
    async def api_delete_watch(
        watch_id: int,
        user: TelegramWebAppUser = Depends(current_user),
    ) -> dict:
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            ok = await repo.deactivate_watch(session, db_user.id, watch_id)
        if not ok:
            raise HTTPException(404, "Подписка не найдена")
        return {"ok": True}

    @app.post("/api/watches/{watch_id}/share")
    async def api_share_watch(
        watch_id: int,
        user: TelegramWebAppUser = Depends(current_user),
    ) -> dict:
        from datetime import timedelta

        from flypingavia.bot.share_tokens import build_share_payload
        from flypingavia.bot.start_payload import build_telegram_start_link

        if not settings.telegram_bot_username:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "BOT_USERNAME_REQUIRED",
                    "message": "Ссылки недоступны: не задан TELEGRAM_BOT_USERNAME.",
                },
            )
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=settings.watch_share_ttl_hours)
        try:
            async with session_scope() as session:
                db_user = await repo.get_or_create_user(
                    session, telegram_id=user.id, username=user.username
                )
                _row, raw = await repo.create_watch_share_token(
                    session,
                    watch_id=watch_id,
                    owner_user_id=db_user.id,
                    expires_at=expires,
                    max_uses=settings.watch_share_max_uses,
                    now=now,
                )
                payload = build_share_payload(raw)
                url = build_telegram_start_link(
                    bot_username=settings.telegram_bot_username,
                    payload=payload,
                )
        except LookupError as exc:
            raise HTTPException(404, "Подписка не найдена") from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "SHARE_LINK_UNAVAILABLE",
                    "message": "Не удалось создать ссылку.",
                },
            ) from exc
        logger.info("Watch share created via API: watch_id=%s", watch_id)
        return {
            "url": url,
            "expires_at": expires.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    @app.delete("/api/watches/{watch_id}/shares")
    async def api_revoke_watch_shares(
        watch_id: int,
        user: TelegramWebAppUser = Depends(current_user),
    ) -> dict:
        now = datetime.now(timezone.utc)
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            n = await repo.revoke_all_watch_shares(
                session,
                watch_id=watch_id,
                owner_user_id=db_user.id,
                now=now,
            )
        if n == 0:
            # либо нет ссылок, либо чужой/несуществующий Watch
            async with session_scope() as session:
                db_user = await repo.get_or_create_user(
                    session, telegram_id=user.id, username=user.username
                )
                own = await repo.get_watch_for_user(
                    session, watch_id=watch_id, user_id=db_user.id
                )
            if own is None:
                raise HTTPException(404, "Подписка не найдена")
        logger.info("Watch shares revoked via API: watch_id=%s count=%s", watch_id, n)
        return {"revoked": n}

    return app
