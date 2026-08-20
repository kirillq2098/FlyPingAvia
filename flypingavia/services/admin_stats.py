"""Read-only aggregates for Telegram admin dashboard (no side effects)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flypingavia.db.models import (
    AlertEvent,
    BetaBug,
    BetaParticipant,
    BetaSurvey,
    User,
    Watch,
)
from flypingavia.monitoring.heartbeat import get_runtime_state
from flypingavia.monitoring.keys import COMPONENT_PRICE_CHECKER


PAGE_SIZE = 10


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_source(raw: str | None) -> str:
    """First-touch source label for admin UI."""
    if raw is None or not str(raw).strip():
        return "direct"
    value = str(raw).strip().lower()
    mapping = {
        "beta_site1": "site1",
        "site1": "site1",
        "beta_ig1": "ig1",
        "ig1": "ig1",
        "beta_w1": "w1",
        "w1": "w1",
        "share": "share",
    }
    return mapping.get(value, value)


@dataclass(frozen=True)
class MainSummary:
    users: int
    active_watches: int
    alerts_24h: int
    new_users_24h: int
    open_bugs: int


@dataclass(frozen=True)
class UsersSummary:
    total: int
    new_24h: int
    new_7d: int
    with_watches: int
    with_active_watches: int
    with_alerts: int
    page: int
    pages: int
    items: list[dict[str, Any]]


@dataclass(frozen=True)
class WatchesSummary:
    total: int
    active: int
    created_24h: int
    created_7d: int
    page: int
    pages: int
    items: list[dict[str, Any]]


@dataclass(frozen=True)
class FunnelSummary:
    users: int
    with_watch: int
    with_alert: int
    active_watches: int
    new_users_7d: int
    first_watch_7d: int
    first_alert_7d: int


@dataclass(frozen=True)
class SourceBucket:
    key: str
    users: int
    with_watch: int
    with_alert: int


@dataclass(frozen=True)
class AlertsSummary:
    total: int
    last_24h: int
    last_7d: int
    unique_users: int
    page: int
    pages: int
    items: list[dict[str, Any]]


@dataclass(frozen=True)
class SystemSummary:
    api_ok: bool | None
    bot_ok: bool | None
    checker_ok: bool | None
    beta_dispatcher_ok: bool | None
    database_ok: bool | None
    version: str
    last_checker_at: datetime | None
    next_checker_at: datetime | None
    active_watches: int
    last_beta_dispatcher_at: datetime | None
    beta_enabled: bool
    checker_interval_seconds: int
    beta_interval_seconds: int


async def fetch_main_summary(session: AsyncSession) -> MainSummary:
    now = _utcnow()
    day_ago = now - timedelta(hours=24)
    users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    active_watches = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.is_active.is_(True))
        )
        or 0
    )
    alerts_24h = int(
        await session.scalar(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.sent_at >= day_ago)
        )
        or 0
    )
    new_users_24h = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= day_ago)
        )
        or 0
    )
    open_bugs = int(
        await session.scalar(
            select(func.count()).select_from(BetaBug).where(BetaBug.status == "open")
        )
        or 0
    )
    return MainSummary(
        users=users,
        active_watches=active_watches,
        alerts_24h=alerts_24h,
        new_users_24h=new_users_24h,
        open_bugs=open_bugs,
    )


async def _maps_for_users(
    session: AsyncSession, user_ids: list[int]
) -> tuple[dict[int, tuple[int, int]], dict[int, int], dict[int, str]]:
    watches: dict[int, tuple[int, int]] = {uid: (0, 0) for uid in user_ids}
    alerts: dict[int, int] = {uid: 0 for uid in user_ids}
    cohorts: dict[int, str] = {}
    if not user_ids:
        return watches, alerts, cohorts

    w_rows = await session.execute(
        select(
            Watch.user_id,
            func.count().label("total"),
            func.sum(case((Watch.is_active.is_(True), 1), else_=0)).label("active"),
        )
        .where(Watch.user_id.in_(user_ids))
        .group_by(Watch.user_id)
    )
    for row in w_rows:
        watches[int(row.user_id)] = (int(row.total or 0), int(row.active or 0))

    a_rows = await session.execute(
        select(AlertEvent.user_id, func.count().label("n"))
        .where(AlertEvent.user_id.in_(user_ids))
        .group_by(AlertEvent.user_id)
    )
    for row in a_rows:
        alerts[int(row.user_id)] = int(row.n or 0)

    c_rows = await session.execute(
        select(BetaParticipant.user_id, BetaParticipant.cohort_code).where(
            BetaParticipant.user_id.in_(user_ids)
        )
    )
    for row in c_rows:
        cohorts[int(row.user_id)] = str(row.cohort_code)

    return watches, alerts, cohorts


async def fetch_users_summary(session: AsyncSession, *, page: int = 0) -> UsersSummary:
    now = _utcnow()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    page = max(0, int(page))

    total = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    new_24h = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= day_ago)
        )
        or 0
    )
    new_7d = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )
        or 0
    )
    with_watches = int(
        await session.scalar(select(func.count(func.distinct(Watch.user_id)))) or 0
    )
    with_active = int(
        await session.scalar(
            select(func.count(func.distinct(Watch.user_id))).where(Watch.is_active.is_(True))
        )
        or 0
    )
    with_alerts = int(
        await session.scalar(select(func.count(func.distinct(AlertEvent.user_id)))) or 0
    )

    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    if page >= pages:
        page = pages - 1

    rows = (
        await session.execute(
            select(User)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).scalars().all()

    ids = [int(u.id) for u in rows]
    watches, alerts, cohorts = await _maps_for_users(session, ids)
    items: list[dict[str, Any]] = []
    for u in rows:
        wt, wa = watches.get(int(u.id), (0, 0))
        items.append(
            {
                "id": int(u.id),
                "username": u.username,
                "created_at": _aware(u.created_at),
                "first_start_source": u.first_start_source,
                "source": normalize_source(u.first_start_source),
                "cohort": cohorts.get(int(u.id)),
                "watches": wt,
                "active_watches": wa,
                "alerts": alerts.get(int(u.id), 0),
            }
        )
    return UsersSummary(
        total=total,
        new_24h=new_24h,
        new_7d=new_7d,
        with_watches=with_watches,
        with_active_watches=with_active,
        with_alerts=with_alerts,
        page=page,
        pages=pages,
        items=items,
    )


async def fetch_user_detail(
    session: AsyncSession, *, user_id: int | None = None, username: str | None = None
) -> dict[str, Any] | None:
    user: User | None = None
    if user_id is not None:
        user = await session.get(User, int(user_id))
    elif username:
        uname = username.lstrip("@").strip()
        if uname:
            user = (
                await session.execute(
                    select(User).where(func.lower(User.username) == uname.lower())
                )
            ).scalar_one_or_none()
    if user is None:
        return None

    uid = int(user.id)
    part = await session.get(BetaParticipant, uid)
    survey = (
        await session.execute(
            select(BetaSurvey).where(
                BetaSurvey.user_id == uid, BetaSurvey.survey_key == "A"
            )
        )
    ).scalar_one_or_none()
    bugs = int(
        await session.scalar(
            select(func.count()).select_from(BetaBug).where(BetaBug.status == "open", BetaBug.user_id == uid)
        )
        or 0
    )
    watches_total = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.user_id == uid)
        )
        or 0
    )
    watches_active = int(
        await session.scalar(
            select(func.count())
            .select_from(Watch)
            .where(Watch.user_id == uid, Watch.is_active.is_(True))
        )
        or 0
    )
    first_watch, last_watch = (
        await session.execute(
            select(func.min(Watch.created_at), func.max(Watch.created_at)).where(
                Watch.user_id == uid
            )
        )
    ).one()
    alerts_total = int(
        await session.scalar(
            select(func.count()).select_from(AlertEvent).where(AlertEvent.user_id == uid)
        )
        or 0
    )
    first_alert, last_alert = (
        await session.execute(
            select(func.min(AlertEvent.sent_at), func.max(AlertEvent.sent_at)).where(
                AlertEvent.user_id == uid
            )
        )
    ).one()

    return {
        "id": uid,
        "username": user.username,
        "created_at": _aware(user.created_at),
        "first_start_source": user.first_start_source,
        "last_start_source": user.last_start_source,
        "source": normalize_source(user.first_start_source),
        "last_source": normalize_source(user.last_start_source)
        if user.last_start_source
        else None,
        "cohort": part.cohort_code if part else None,
        "consent_at": _aware(part.consent_at) if part else None,
        "joined_at": _aware(part.joined_at) if part else None,
        "watches": watches_total,
        "active_watches": watches_active,
        "alerts": alerts_total,
        "first_watch": _aware(first_watch),
        "last_watch": _aware(last_watch),
        "first_alert": _aware(first_alert),
        "last_alert": _aware(last_alert),
        "survey_a": survey.status if survey else None,
        "bugs_open": bugs,
    }


async def fetch_watches_summary(session: AsyncSession, *, page: int = 0) -> WatchesSummary:
    now = _utcnow()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    page = max(0, int(page))

    total = int(await session.scalar(select(func.count()).select_from(Watch)) or 0)
    active = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.is_active.is_(True))
        )
        or 0
    )
    created_24h = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.created_at >= day_ago)
        )
        or 0
    )
    created_7d = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.created_at >= week_ago)
        )
        or 0
    )
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    if page >= pages:
        page = pages - 1

    rows = (
        await session.execute(
            select(Watch)
            .options(selectinload(Watch.user))
            .order_by(Watch.created_at.desc(), Watch.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).scalars().all()

    items: list[dict[str, Any]] = []
    for w in rows:
        items.append(
            {
                "id": int(w.id),
                "origin": w.origin,
                "destination": w.destination,
                "depart_date": w.depart_date,
                "return_date": w.return_date,
                "max_price": w.max_price,
                "last_price": w.last_price,
                "currency": w.currency or "RUB",
                "is_active": bool(w.is_active),
                "created_at": _aware(w.created_at),
                "username": w.user.username if w.user else None,
                "user_id": int(w.user_id),
            }
        )
    return WatchesSummary(
        total=total,
        active=active,
        created_24h=created_24h,
        created_7d=created_7d,
        page=page,
        pages=pages,
        items=items,
    )


async def fetch_funnel_summary(session: AsyncSession) -> FunnelSummary:
    now = _utcnow()
    week_ago = now - timedelta(days=7)
    users = int(await session.scalar(select(func.count()).select_from(User)) or 0)
    with_watch = int(
        await session.scalar(select(func.count(func.distinct(Watch.user_id)))) or 0
    )
    with_alert = int(
        await session.scalar(select(func.count(func.distinct(AlertEvent.user_id)))) or 0
    )
    active_watches = int(
        await session.scalar(
            select(func.count()).select_from(Watch).where(Watch.is_active.is_(True))
        )
        or 0
    )
    new_users_7d = int(
        await session.scalar(
            select(func.count()).select_from(User).where(User.created_at >= week_ago)
        )
        or 0
    )
    # Users whose first watch was created in last 7d
    first_watch_subq = (
        select(Watch.user_id, func.min(Watch.created_at).label("first_at"))
        .group_by(Watch.user_id)
        .subquery()
    )
    first_watch_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(first_watch_subq)
            .where(first_watch_subq.c.first_at >= week_ago)
        )
        or 0
    )
    first_alert_subq = (
        select(AlertEvent.user_id, func.min(AlertEvent.sent_at).label("first_at"))
        .group_by(AlertEvent.user_id)
        .subquery()
    )
    first_alert_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(first_alert_subq)
            .where(first_alert_subq.c.first_at >= week_ago)
        )
        or 0
    )
    return FunnelSummary(
        users=users,
        with_watch=with_watch,
        with_alert=with_alert,
        active_watches=active_watches,
        new_users_7d=new_users_7d,
        first_watch_7d=first_watch_7d,
        first_alert_7d=first_alert_7d,
    )


async def fetch_source_buckets(session: AsyncSession) -> list[SourceBucket]:
    """Acquisition by first_start_source (normalized). Does not mix beta cohort."""
    users = (await session.execute(select(User))).scalars().all()
    watch_users = set(
        int(r)
        for r in (
            await session.execute(select(func.distinct(Watch.user_id)))
        ).scalars().all()
    )
    alert_users = set(
        int(r)
        for r in (
            await session.execute(select(func.distinct(AlertEvent.user_id)))
        ).scalars().all()
    )

    buckets: dict[str, dict[str, int]] = {}
    order = ["site1", "ig1", "w1", "share", "direct"]
    for u in users:
        key = normalize_source(u.first_start_source)
        if key not in buckets:
            buckets[key] = {"users": 0, "with_watch": 0, "with_alert": 0}
        buckets[key]["users"] += 1
        if int(u.id) in watch_users:
            buckets[key]["with_watch"] += 1
        if int(u.id) in alert_users:
            buckets[key]["with_alert"] += 1

    result: list[SourceBucket] = []
    seen: set[str] = set()
    for key in order:
        if key in buckets:
            b = buckets[key]
            result.append(
                SourceBucket(
                    key=key,
                    users=b["users"],
                    with_watch=b["with_watch"],
                    with_alert=b["with_alert"],
                )
            )
            seen.add(key)
    for key in sorted(k for k in buckets if k not in seen):
        b = buckets[key]
        result.append(
            SourceBucket(
                key=key,
                users=b["users"],
                with_watch=b["with_watch"],
                with_alert=b["with_alert"],
            )
        )
    return result


async def fetch_alerts_summary(session: AsyncSession, *, page: int = 0) -> AlertsSummary:
    now = _utcnow()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)
    page = max(0, int(page))

    total = int(await session.scalar(select(func.count()).select_from(AlertEvent)) or 0)
    last_24h = int(
        await session.scalar(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.sent_at >= day_ago)
        )
        or 0
    )
    last_7d = int(
        await session.scalar(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.sent_at >= week_ago)
        )
        or 0
    )
    unique_users = int(
        await session.scalar(select(func.count(func.distinct(AlertEvent.user_id)))) or 0
    )
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    if page >= pages:
        page = pages - 1

    rows = (
        await session.execute(
            select(AlertEvent)
            .options(selectinload(AlertEvent.watch))
            .order_by(AlertEvent.sent_at.desc(), AlertEvent.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).scalars().all()

    user_ids = list({int(a.user_id) for a in rows})
    usernames: dict[int, str | None] = {}
    if user_ids:
        for u in (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all():
            usernames[int(u.id)] = u.username

    items: list[dict[str, Any]] = []
    for a in rows:
        w = a.watch
        items.append(
            {
                "id": int(a.id),
                "username": usernames.get(int(a.user_id)),
                "user_id": int(a.user_id),
                "origin": w.origin if w else "—",
                "destination": w.destination if w else "—",
                "price": a.price,
                "threshold": a.threshold,
                "currency": a.currency or "RUB",
                "sent_at": _aware(a.sent_at),
            }
        )
    return AlertsSummary(
        total=total,
        last_24h=last_24h,
        last_7d=last_7d,
        unique_users=unique_users,
        page=page,
        pages=pages,
        items=items,
    )


async def fetch_open_bugs(
    session: AsyncSession, *, page: int = 0
) -> tuple[int, int, int, list[dict[str, Any]]]:
    page = max(0, int(page))
    total = int(
        await session.scalar(
            select(func.count()).select_from(BetaBug).where(BetaBug.status == "open")
        )
        or 0
    )
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    if page >= pages:
        page = pages - 1
    rows = (
        await session.execute(
            select(BetaBug)
            .where(BetaBug.status == "open")
            .order_by(BetaBug.created_at.desc(), BetaBug.id.desc())
            .offset(page * PAGE_SIZE)
            .limit(PAGE_SIZE)
        )
    ).scalars().all()
    user_ids = list({int(b.user_id) for b in rows})
    usernames: dict[int, str | None] = {}
    if user_ids:
        for u in (
            await session.execute(select(User).where(User.id.in_(user_ids)))
        ).scalars().all():
            usernames[int(u.id)] = u.username
    items = [
        {
            "id": int(b.id),
            "username": usernames.get(int(b.user_id)),
            "severity": b.severity,
            "status": b.status,
            "created_at": _aware(b.created_at),
            "what_happened": (b.what_happened or "")[:120],
        }
        for b in rows
    ]
    return total, page, pages, items


async def fetch_system_summary(
    session: AsyncSession,
    *,
    version: str,
    beta_enabled: bool,
    checker_interval_seconds: int,
    beta_interval_seconds: int,
    checker_stale_after_seconds: int,
) -> SystemSummary:
    database_ok: bool | None = None
    api_ok: bool | None = None
    try:
        await session.execute(text("SELECT 1"))
        database_ok = True
        api_ok = True
    except Exception:
        database_ok = False
        api_ok = False

    checker_ok: bool | None = None
    last_checker: datetime | None = None
    next_checker: datetime | None = None
    try:
        state = await get_runtime_state(session, component_key=COMPONENT_PRICE_CHECKER)
        if state is None:
            checker_ok = None
        else:
            last_checker = _aware(state.last_success_at or state.last_completed_at)
            completed = _aware(state.last_completed_at)
            if completed is not None:
                age = (_utcnow() - completed).total_seconds()
                checker_ok = age < float(checker_stale_after_seconds)
                next_checker = completed + timedelta(seconds=int(checker_interval_seconds))
            else:
                checker_ok = None
    except Exception:
        checker_ok = None

    active_watches = 0
    try:
        active_watches = int(
            await session.scalar(
                select(func.count()).select_from(Watch).where(Watch.is_active.is_(True))
            )
            or 0
        )
    except Exception:
        pass

    # No dedicated heartbeat for beta dispatcher — do not fake green.
    beta_dispatcher_ok: bool | None = True if beta_enabled else None
    last_beta: datetime | None = None

    return SystemSummary(
        api_ok=api_ok,
        bot_ok=True,  # reached from live bot handler
        checker_ok=checker_ok,
        beta_dispatcher_ok=beta_dispatcher_ok if beta_enabled else None,
        database_ok=database_ok,
        version=version,
        last_checker_at=last_checker,
        next_checker_at=next_checker,
        active_watches=active_watches,
        last_beta_dispatcher_at=last_beta,
        beta_enabled=beta_enabled,
        checker_interval_seconds=int(checker_interval_seconds),
        beta_interval_seconds=int(beta_interval_seconds),
    )
