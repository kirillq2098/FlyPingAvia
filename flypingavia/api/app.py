from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

from fastapi import Body, Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from flypingavia.api.telegram_auth import (
    TelegramAuthError,
    TelegramWebAppUser,
    validate_telegram_init_data,
)
from flypingavia.config import Settings, get_settings
from flypingavia.diagnostics.miniapp_session import (
    mask_ip,
    sanitize_ua,
    utc_now_iso,
    write_diag_event,
)
from flypingavia.version import __version__
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services.locations import resolve_place
from flypingavia.services.prices import build_affiliate_url, build_price_provider
from flypingavia.services.flexible_dates import search_flexible_trip, validate_flexibility_days
from flypingavia.services.threshold_policy import (
    band_from_snapshot,
    evaluate_low_threshold,
)
from flypingavia.bot.formatters import money as format_money

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "web" / "static"


class MiniAppDiagIn(BaseModel):
    """Safe client bootstrap diagnostics — no secrets / initData / Telegram IDs."""

    session_id: str = ""
    event: str = ""
    stage: str = "unknown"
    boot_state: str = ""
    has_init_data: bool = False
    init_data_len: int = 0
    has_cached_init: bool = False
    inside_telegram: bool = False
    ui_started: bool = False
    elapsed_ms: int = 0
    endpoint: str = ""
    http_status: int = 0
    error_code: str = ""
    # Launch URL / SDK signals (names/flags only)
    has_telegram: bool = False
    has_webapp: bool = False
    platform: str = ""
    sdk_fallback: bool = False
    sdk_source: str = ""
    asset: str = ""
    launch_mode: str = ""
    unsafe_keys: str = ""
    unsafe_has_user: bool = False
    hash_present: bool = False
    hash_len: int = 0
    hash_params: str = ""
    hash_param_lens: str = ""
    search_present: bool = False
    search_len: int = 0
    search_params: str = ""
    search_param_lens: str = ""
    has_tgwebappdata: bool = False
    tgwebappdata_len: int = 0
    has_tgwebappversion: bool = False
    has_tgwebappplatform: bool = False
    has_tgwebapptheme: bool = False
    decode_ok: bool = True
    decode_passes: int = 0
    extract_ok: bool = False
    extract_source: str = ""
    extract_len: int = 0
    spa_path: bool = False
    sdk_init_len: int = 0
    storage_present: bool = False
    href_len: int = 0
    path: str = ""
    origin: str = ""
    referrer_origin: str = ""
    referrer_path: str = ""
    has_webview_proxy: bool = False
    has_telegram_webview: bool = False
    nav_type: str = ""
    visibility: str = ""
    ready_state: str = ""
    online: bool = True
    url_changed: bool = False
    ready_called: bool = False
    expand_called: bool = False
    webapp_version: str = ""
    color_scheme: str = ""
    is_expanded: bool = False
    viewport_height: int = 0
    viewport_stable_height: int = 0
    # Browser / device (safe)
    ua: str = ""
    nav_platform: str = ""
    nav_vendor: str = ""
    language: str = ""
    languages: str = ""
    ua_data_present: bool = False
    ua_brands: str = ""
    ua_platform: str = ""
    screen_w: int = 0
    screen_h: int = 0
    dpr: float = 0
    timezone: str = ""
    cookie_enabled: bool = False
    local_storage_ok: bool = False
    session_storage_ok: bool = False
    detail: str = ""


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
    price_source: Optional[str] = None  # live_search | travelpayouts_estimate
    is_live: bool = False
    updated_at: Optional[str] = None
    fallback_reason: Optional[str] = None  # live_timeout | live_access_denied | live_provider_error | live_no_results
    market_band_source: Optional[str] = None
    # CS-07 MVP flexible window metadata
    flexibility_days: int = 0
    primary_depart_date: Optional[date] = None
    primary_return_date: Optional[date] = None
    found_depart_date: Optional[date] = None
    found_return_date: Optional[date] = None
    offset_days: int = 0
    # Quote cache / progressive metadata (additive, backward compatible)
    cached: bool = False
    stale: bool = False
    partial: bool = False
    refreshing: bool = False
    cache_age_seconds: Optional[int] = None
    computed_at: Optional[str] = None
    status: Optional[str] = None  # fresh|stale|live|partial|timeout
    combinations_count: Optional[int] = None
    completed_count: Optional[int] = None
    title: str = "Ориентир по стоимости"


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
    # Optional market snapshot from prior /api/quote — avoids re-search on create.
    market_cheap_max: Optional[float] = None
    market_typical: Optional[float] = None
    market_expensive_min: Optional[float] = None


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
        request: Request,
        authorization: Annotated[str | None, Header()] = None,
        x_telegram_init_data: Annotated[str | None, Header()] = None,
        x_diag_session: Annotated[str | None, Header()] = None,
    ) -> TelegramWebAppUser:
        """Единая dependency: только проверенный initData (или dev user вне production)."""
        session_id = (x_diag_session or "").strip()[:64]
        client_ip = request.client.host if request.client else ""

        def _auth_fail(code: str, status: int = 401) -> None:
            write_diag_event(
                {
                    "kind": "backend",
                    "event": "api_me_error",
                    "stage": "api_me_error",
                    "session_id": session_id,
                    "endpoint": str(request.url.path)[:64],
                    "path": str(request.url.path)[:64],
                    "http_status": status,
                    "status": status,
                    "error_code": code[:64],
                    "client_ip_masked": mask_ip(client_ip),
                    "ua_sanitized": sanitize_ua(request.headers.get("user-agent")),
                    "ts": utc_now_iso(),
                }
            )

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
                _auth_fail(exc.code)
                raise HTTPException(status_code=401, detail=exc.as_detail()) from exc
            logger.debug("Telegram Mini App auth ok user_id=%s", user.id)
            return user

        # Без initData: только development/test + WEBAPP_DEV_USER_ID > 0
        if settings.is_production:
            _auth_fail("MISSING_INIT_DATA")
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
        # index.html must not be cached by Telegram WebView / browsers
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )

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
    async def me(
        request: Request,
        user: TelegramWebAppUser = Depends(current_user),
        x_diag_session: Annotated[str | None, Header()] = None,
    ) -> dict:
        # Первый валидный запуск Mini App — создать/обновить User (username).
        session_id = (x_diag_session or "").strip()[:64]
        client_ip = request.client.host if request.client else ""
        write_diag_event(
            {
                "kind": "backend",
                "event": "api_me_start",
                "stage": "api_me_start",
                "session_id": session_id,
                "endpoint": "/api/me",
                "path": "/api/me",
                "client_ip_masked": mask_ip(client_ip),
                "ua_sanitized": sanitize_ua(request.headers.get("user-agent")),
                "ts": utc_now_iso(),
            }
        )
        try:
            async with session_scope() as session:
                await repo.get_or_create_user(
                    session, telegram_id=user.id, username=user.username
                )
        except Exception:
            write_diag_event(
                {
                    "kind": "backend",
                    "event": "api_me_error",
                    "stage": "api_me_error",
                    "session_id": session_id,
                    "endpoint": "/api/me",
                    "path": "/api/me",
                    "http_status": 500,
                    "status": 500,
                    "error_code": "server_error",
                    "client_ip_masked": mask_ip(client_ip),
                    "ts": utc_now_iso(),
                }
            )
            raise
        write_diag_event(
            {
                "kind": "backend",
                "event": "api_me_response",
                "stage": "api_me_ok",
                "session_id": session_id,
                "endpoint": "/api/me",
                "path": "/api/me",
                "http_status": 200,
                "status": 200,
                "client_ip_masked": mask_ip(client_ip),
                "ts": utc_now_iso(),
            }
        )
        return {
            "telegram_user_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
        }

    @app.post("/api/diag/miniapp-bootstrap")
    async def diag_miniapp_bootstrap(
        request: Request,
        body: MiniAppDiagIn = Body(default_factory=MiniAppDiagIn),
    ) -> dict:
        """BUG-02.5: безопасная диагностика bootstrap + JSONL session log."""
        stage = (body.event or body.stage or "unknown")[:64]
        init_len = body.init_data_len if 0 <= body.init_data_len <= 100000 else 0
        elapsed = body.elapsed_ms if 0 <= body.elapsed_ms <= 600000 else 0
        endpoint = (body.endpoint or "")[:64]
        error_code = (body.error_code or "")[:64]
        session_id = (body.session_id or "")[:64]
        client_ip = request.client.host if request.client else ""
        logger.info(
            "miniapp_diag sid=%s stage=%s boot=%s has_init=%s init_len=%s mode=%s "
            "asset=%s platform=%s tgdata=%s/%s extract_ok=%s elapsed_ms=%s",
            session_id or "-",
            stage,
            (body.boot_state or "-")[:32],
            bool(body.has_init_data),
            init_len,
            (body.launch_mode or "-")[:32],
            (body.asset or "-")[:32],
            (body.platform or "-")[:32],
            bool(body.has_tgwebappdata),
            int(body.tgwebappdata_len or 0),
            bool(body.extract_ok),
            elapsed,
        )
        write_diag_event(
            {
                "kind": "frontend",
                "ts": utc_now_iso(),
                "session_id": session_id,
                "event": stage,
                "stage": stage,
                "boot_state": (body.boot_state or "")[:32],
                "has_init_data": bool(body.has_init_data),
                "init_data_len": init_len,
                "has_cached_init": bool(body.has_cached_init),
                "inside_telegram": bool(body.inside_telegram),
                "ui_started": bool(body.ui_started),
                "elapsed_ms": elapsed,
                "endpoint": endpoint,
                "http_status": int(body.http_status or 0),
                "error_code": error_code,
                "has_telegram": bool(body.has_telegram),
                "has_webapp": bool(body.has_webapp),
                "platform": (body.platform or "")[:32],
                "sdk_fallback": bool(body.sdk_fallback),
                "sdk_source": (body.sdk_source or "")[:16],
                "asset": (body.asset or "")[:32],
                "launch_mode": (body.launch_mode or "")[:32],
                "unsafe_keys": (body.unsafe_keys or "")[:120],
                "unsafe_has_user": bool(body.unsafe_has_user),
                "hash_present": bool(body.hash_present),
                "hash_len": int(body.hash_len or 0),
                "hash_params": (body.hash_params or "")[:120],
                "hash_param_lens": (body.hash_param_lens or "")[:200],
                "search_present": bool(body.search_present),
                "search_len": int(body.search_len or 0),
                "search_params": (body.search_params or "")[:120],
                "search_param_lens": (body.search_param_lens or "")[:200],
                "has_tgwebappdata": bool(body.has_tgwebappdata),
                "tgwebappdata_len": int(body.tgwebappdata_len or 0),
                "has_tgwebappversion": bool(body.has_tgwebappversion),
                "has_tgwebappplatform": bool(body.has_tgwebappplatform),
                "has_tgwebapptheme": bool(body.has_tgwebapptheme),
                "decode_ok": bool(body.decode_ok),
                "decode_passes": int(body.decode_passes or 0),
                "extract_ok": bool(body.extract_ok),
                "extract_source": (body.extract_source or "")[:32],
                "extract_len": int(body.extract_len or 0),
                "spa_path": bool(body.spa_path),
                "sdk_init_len": int(body.sdk_init_len or 0),
                "storage_present": bool(body.storage_present),
                "href_len": int(body.href_len or 0),
                "path": (body.path or "")[:64],
                "origin": (body.origin or "")[:64],
                "referrer_origin": (body.referrer_origin or "")[:64],
                "referrer_path": (body.referrer_path or "")[:64],
                "has_webview_proxy": bool(body.has_webview_proxy),
                "has_telegram_webview": bool(body.has_telegram_webview),
                "nav_type": (body.nav_type or "")[:32],
                "visibility": (body.visibility or "")[:32],
                "ready_state": (body.ready_state or "")[:32],
                "online": bool(body.online),
                "url_changed": bool(body.url_changed),
                "ready_called": bool(body.ready_called),
                "expand_called": bool(body.expand_called),
                "webapp_version": (body.webapp_version or "")[:16],
                "color_scheme": (body.color_scheme or "")[:16],
                "is_expanded": bool(body.is_expanded),
                "viewport_height": int(body.viewport_height or 0),
                "viewport_stable_height": int(body.viewport_stable_height or 0),
                "ua": sanitize_ua(body.ua),
                "ua_sanitized": sanitize_ua(body.ua),
                "nav_platform": (body.nav_platform or "")[:64],
                "nav_vendor": (body.nav_vendor or "")[:64],
                "language": (body.language or "")[:32],
                "languages": (body.languages or "")[:120],
                "ua_data_present": bool(body.ua_data_present),
                "ua_brands": (body.ua_brands or "")[:120],
                "ua_platform": (body.ua_platform or "")[:64],
                "screen_w": int(body.screen_w or 0),
                "screen_h": int(body.screen_h or 0),
                "dpr": float(body.dpr or 0),
                "timezone": (body.timezone or "")[:64],
                "cookie_enabled": bool(body.cookie_enabled),
                "local_storage_ok": bool(body.local_storage_ok),
                "session_storage_ok": bool(body.session_storage_ok),
                "detail": (body.detail or "")[:200],
                "client_ip_masked": mask_ip(client_ip),
            }
        )
        return {"ok": True}

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
        refresh: bool = Query(default=False),
        user: TelegramWebAppUser = Depends(current_user),
    ) -> QuoteOut:
        import time

        from flypingavia.services.quote_cache import (
            default_quote_cache,
            make_quote_cache_key,
        )
        LIVE_FRESH_TTL_SECONDS = 60
        LIVE_STALE_TTL_SECONDS = 120

        def _normalize_cache_status(
            original: str,
            entry_data: dict | None,
            age_seconds: int | None,
        ) -> str:
            if original == "miss":
                return "miss"
            if not entry_data:
                return original
            src = (entry_data.get("price_source") or entry_data.get("source") or "").lower()
            is_live_src = src == "live_search"
            if not is_live_src:
                return original
            age = int(age_seconds or 0)
            if age <= LIVE_FRESH_TTL_SECONDS:
                return "fresh"
            if age <= LIVE_STALE_TTL_SECONDS:
                return "stale"
            return "miss"

        _ = user
        t0 = time.monotonic()
        logger.info(
            "quote.request.started origin=%s destination=%s flex=%s refresh=%s",
            (origin or "").upper()[:16],
            (destination or "").upper()[:16],
            flexibility_days,
            refresh,
        )
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

        trip_type = "round" if return_date else "oneway"
        provider_name = "demo" if settings.is_demo_prices else "travelpayouts"
        cache_key = make_quote_cache_key(
            origin=origin_place.code,
            destination=dest_place.code,
            origin_search=",".join(origin_place.search_codes),
            destination_search=",".join(dest_place.search_codes),
            depart_date=depart_date,
            return_date=return_date,
            flexibility_days=flex,
            adults=adults,
            children=children,
            infants=infants,
            currency=settings.currency,
            trip_type=trip_type,
            provider=provider_name,
        )
        cache = default_quote_cache
        entry, status = cache.lookup(cache_key)
        status = _normalize_cache_status(
            status,
            (entry.data if entry else None),
            (entry.age_seconds if entry else None),
        )
        if status == "fresh" and not refresh:
            cache.metrics.cache_hits += 1
            cache.metrics.record_latency((time.monotonic() - t0) * 1000)
            logger.info(
                "quote.cache.hit key=%s age_s=%s duration_ms=%.0f",
                cache_key[:12],
                entry.age_seconds if entry else None,
                (time.monotonic() - t0) * 1000,
            )
            assert entry is not None
            data = dict(entry.data)
            data.update(
                {
                    "cached": True,
                    "stale": False,
                    "refreshing": False,
                    "cache_age_seconds": entry.age_seconds,
                    "computed_at": entry.computed_at_iso,
                    "updated_at": entry.computed_at_iso,
                    "status": "fresh",
                }
            )
            logger.info("quote.response.completed status=fresh duration_ms=%.0f", (time.monotonic() - t0) * 1000)
            return QuoteOut.model_validate(data)

        if status == "stale" and not refresh and entry is not None:
            cache.metrics.cache_hits += 1
            cache.metrics.stale_serves += 1
            cache.metrics.record_latency((time.monotonic() - t0) * 1000)
            logger.info(
                "quote.cache.hit stale=1 key=%s age_s=%s duration_ms=%.0f",
                cache_key[:12],
                entry.age_seconds,
                (time.monotonic() - t0) * 1000,
            )
            data = dict(entry.data)
            data.update(
                {
                    "cached": True,
                    "stale": True,
                    "refreshing": True,
                    "cache_age_seconds": entry.age_seconds,
                    "computed_at": entry.computed_at_iso,
                    "updated_at": entry.computed_at_iso,
                    "status": "stale",
                }
            )
            logger.info("quote.response.completed status=stale duration_ms=%.0f", (time.monotonic() - t0) * 1000)
            return QuoteOut.model_validate(data)

        cache.metrics.cache_misses += 1
        logger.info("quote.cache.miss key=%s", cache_key[:12])

        async def _compute() -> dict:
            logger.info(
                "quote.provider.started provider=%s route=%s→%s flex=%s",
                provider_name,
                origin_place.code,
                dest_place.code,
                flex,
            )
            prov_t0 = time.monotonic()
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
                prefer_live_for_quote=True,
            )
            logger.info(
                "quote.provider.completed duration_ms=%.0f combinations=%s completed=%s partial=%s",
                (time.monotonic() - prov_t0) * 1000,
                getattr(result, "combinations_count", None) if result else 0,
                getattr(result, "completed_count", None) if result else 0,
                getattr(result, "partial", False) if result else False,
            )
            quote = result.quote if result else None
            band = result.band if result else None
            found_dep = result.found_depart_date if result else depart_date
            found_ret = result.found_return_date if result else return_date
            offset = result.offset_days if result else 0
            partial = bool(result.partial) if result else False
            combinations_count = result.combinations_count if result else 0
            completed_count = result.completed_count if result else 0

            level = band.classify(quote.price).value if quote and band else None
            is_live = bool(quote and quote.is_live)
            fallback_reason = quote.fallback_reason if quote else None
            price_source = "live_search" if is_live else ("travelpayouts_estimate" if quote else None)
            note = None
            if origin_place.kind == "city" and len(origin_place.airport_codes) > 1:
                note = f"Проверены аэропорты: {', '.join(origin_place.airport_codes)}"
            if quote and not quote.is_live and fallback_reason:
                extra = "Оценка по данным Travelpayouts"
                note = f"{note}. {extra}" if note else extra

            status_label = "partial" if partial else ("timeout" if quote is None else "live")
            if result is None:
                cache.metrics.timeouts += 1
            if partial:
                cache.metrics.partials += 1
            if combinations_count:
                cache.metrics.combinations.append(int(combinations_count))
            if is_live:
                cache.metrics.live_success += 1
            elif fallback_reason:
                cache.metrics.fallback_used += 1
                if fallback_reason == "live_timeout":
                    cache.metrics.live_timeout += 1
                elif fallback_reason == "live_no_results":
                    cache.metrics.live_no_results += 1
                else:
                    cache.metrics.live_error += 1

            out = QuoteOut(
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
                trip_type=trip_type,
                price_for="passengers" if (quote and quote.is_live) else "adult",
                source=quote.source if quote else None,
                price_source=price_source,
                is_live=is_live,
                updated_at=datetime.now(timezone.utc).isoformat(),
                fallback_reason=fallback_reason,
                market_band_source=(band.source if band else None),
                flexibility_days=flex,
                primary_depart_date=depart_date,
                primary_return_date=return_date,
                found_depart_date=found_dep,
                found_return_date=found_ret,
                offset_days=offset,
                cached=False,
                stale=False,
                partial=partial,
                refreshing=False,
                cache_age_seconds=0,
                computed_at=datetime.now(timezone.utc).isoformat(),
                status=status_label,
                combinations_count=combinations_count,
                completed_count=completed_count,
                title=(
                    "Предварительный ориентир"
                    if partial
                    else ("Минимальная цена сейчас" if is_live else "Оценка стоимости")
                ),
            )
            return out.model_dump(mode="json")

        try:
            raw = await cache.coalesce(cache_key, _compute)
        except Exception:
            cache.metrics.provider_errors += 1
            logger.exception("quote.provider.error")
            raise

        # Cache successful payloads that have a usable band or price.
        if raw.get("price") is not None or raw.get("cheap_max") is not None:
            stored = cache.store(cache_key, raw, provider=provider_name)
            raw = dict(raw)
            raw["computed_at"] = stored.computed_at_iso
            raw["updated_at"] = stored.computed_at_iso
            raw["cache_age_seconds"] = 0

        cache.metrics.record_latency((time.monotonic() - t0) * 1000)
        logger.info(
            "quote.response.completed status=%s duration_ms=%.0f cached=0",
            raw.get("status"),
            (time.monotonic() - t0) * 1000,
        )
        return QuoteOut.model_validate(raw)

    @app.get("/api/metrics/quote")
    async def quote_metrics() -> dict:
        from flypingavia.services.quote_cache import default_quote_cache
        from flypingavia.services.provider_http_cache import default_provider_http_cache

        snap = default_quote_cache.metrics.snapshot()
        http = default_provider_http_cache
        total = http.hits + http.misses
        snap["provider_http_cache_hits"] = http.hits
        snap["provider_http_cache_misses"] = http.misses
        snap["provider_http_cache_hit_rate"] = (
            round(http.hits / total, 4) if total else 0.0
        )
        return {"ok": True, "metrics": snap}

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
        idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    ) -> WatchOut:
        import math

        from sqlalchemy.exc import IntegrityError

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

        idem_key = (idempotency_key or "").strip() or None
        if idem_key is not None and len(idem_key) > 128:
            raise HTTPException(400, "Idempotency-Key слишком длинный")

        # CS-05: prefer quote snapshot from client; skip live re-search when
        # confirmed or snapshot present (create latency hotspot was search_flexible_trip).
        band = None
        if body.market_cheap_max is not None and body.market_typical is not None:
            band = band_from_snapshot(
                cheap_max=body.market_cheap_max,
                typical=body.market_typical,
                expensive_min=body.market_expensive_min,
                currency=settings.currency,
            )
        elif body.confirm_low_threshold:
            band = None
        else:
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
            if idem_key:
                existing = await repo.get_watch_by_idempotency_key(
                    session, user_id=db_user.id, key=idem_key
                )
                if existing is not None:
                    return _watch_out(existing)

            recent = await repo.find_recent_similar_watch(
                session,
                user_id=db_user.id,
                origin=origin_place.code,
                destination=dest_place.code,
                max_price=body.max_price,
                depart_date=body.depart_date,
                return_date=body.return_date,
                flexibility_days=flex,
                adults=body.adults,
                children=body.children,
                infants=body.infants,
                currency=settings.currency,
                within_seconds=60,
            )
            if recent is not None:
                if idem_key:
                    try:
                        async with session.begin_nested():
                            await repo.save_watch_idempotency(
                                session,
                                user_id=db_user.id,
                                key=idem_key,
                                watch_id=recent.id,
                            )
                    except IntegrityError:
                        existing = await repo.get_watch_by_idempotency_key(
                            session, user_id=db_user.id, key=idem_key
                        )
                        if existing is not None:
                            return _watch_out(existing)
                return _watch_out(recent)

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
            if idem_key:
                try:
                    async with session.begin_nested():
                        await repo.save_watch_idempotency(
                            session,
                            user_id=db_user.id,
                            key=idem_key,
                            watch_id=watch.id,
                        )
                except IntegrityError:
                    # Параллельный запрос с тем же ключом уже сохранил mapping —
                    # удаляем наш дубль и возвращаем победителя.
                    await session.delete(watch)
                    await session.flush()
                    existing = await repo.get_watch_by_idempotency_key(
                        session, user_id=db_user.id, key=idem_key
                    )
                    if existing is not None:
                        return _watch_out(existing)
                    raise
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
