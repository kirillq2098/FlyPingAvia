from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flypingavia.db.models import AlertEvent, User, Watch


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: Optional[str] = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username)
        session.add(user)
        await session.flush()
    elif username and user.username != username:
        user.username = username
    return user


async def record_user_start(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    source: Optional[str],
    started_at: datetime,
    username: Optional[str] = None,
) -> User:
    """Записать /start attribution (first-touch / last-touch).

    - first_start_at заполняется только если пуст;
    - first_start_source — только если пуст и source валиден;
    - last_start_at всегда обновляется;
    - last_start_source обновляется только при переданном source;
    - отсутствие/невалидный source не стирает last_start_source.
    """
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    else:
        started_at = started_at.astimezone(timezone.utc)

    user = await get_or_create_user(session, telegram_id=telegram_user_id, username=username)

    if user.first_start_at is None:
        user.first_start_at = started_at
    user.last_start_at = started_at

    if source:
        if user.first_start_source is None:
            user.first_start_source = source
        user.last_start_source = source

    await session.flush()
    return user


async def count_active_watches(session: AsyncSession, user_id: int) -> int:
    result = await session.execute(
        select(Watch).where(Watch.user_id == user_id, Watch.is_active.is_(True))
    )
    return len(result.scalars().all())


async def add_watch(
    session: AsyncSession,
    *,
    user: User,
    origin: str,
    destination: str,
    max_price: float,
    depart_date: Optional[date],
    currency: str = "RUB",
    origin_name: Optional[str] = None,
    destination_name: Optional[str] = None,
    origin_search: Optional[str] = None,
    destination_search: Optional[str] = None,
    return_date: Optional[date] = None,
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    flexibility_days: int = 0,
) -> Watch:
    from flypingavia.services.flexible_dates import validate_flexibility_days

    watch = Watch(
        user_id=user.id,
        origin=origin.upper(),
        destination=destination.upper(),
        origin_name=origin_name,
        destination_name=destination_name,
        origin_search=origin_search or origin.upper(),
        destination_search=destination_search or destination.upper(),
        max_price=max_price,
        depart_date=depart_date,
        return_date=return_date,
        adults=max(1, adults),
        children=max(0, children),
        infants=max(0, infants),
        currency=currency.upper(),
        flexibility_days=validate_flexibility_days(flexibility_days),
    )
    session.add(watch)
    await session.flush()
    return watch


async def list_watches(session: AsyncSession, user_id: int) -> Sequence[Watch]:
    result = await session.execute(
        select(Watch)
        .where(Watch.user_id == user_id, Watch.is_active.is_(True))
        .order_by(Watch.id)
    )
    return result.scalars().all()


async def deactivate_watch(session: AsyncSession, user_id: int, watch_id: int) -> bool:
    result = await session.execute(
        select(Watch).where(
            Watch.id == watch_id,
            Watch.user_id == user_id,
            Watch.is_active.is_(True),
        )
    )
    watch = result.scalar_one_or_none()
    if watch is None:
        return False
    watch.is_active = False
    return True


async def get_active_watches(session: AsyncSession) -> Sequence[Watch]:
    result = await session.execute(
        select(Watch)
        .options(selectinload(Watch.user))
        .where(Watch.is_active.is_(True))
    )
    return result.scalars().all()


async def mark_watch_checked(
    session: AsyncSession,
    watch_id: int,
    checked_at: datetime,
) -> bool:
    """Обновить last_checked_at (UTC) без затирания остальных полей.

    Возвращает False, если Watch удалён/неактивен.
    """
    fresh = await session.get(Watch, watch_id)
    if fresh is None or not fresh.is_active:
        return False
    if checked_at.tzinfo is None:
        checked_at = checked_at.replace(tzinfo=timezone.utc)
    else:
        checked_at = checked_at.astimezone(timezone.utc)
    fresh.last_checked_at = checked_at
    await session.flush()
    return True


async def log_alert_event(
    session: AsyncSession,
    *,
    watch_id: int,
    user_id: int,
    price: float,
    threshold: float,
    currency: str = "RUB",
    sent_at: datetime | None = None,
) -> AlertEvent:
    """Писать только после успешной отправки сообщения пользователю."""
    event = AlertEvent(
        watch_id=watch_id,
        user_id=user_id,
        price=price,
        threshold=threshold,
        currency=(currency or "RUB").upper(),
        sent_at=sent_at or datetime.now(timezone.utc),
    )
    session.add(event)
    await session.flush()
    return event


async def get_latest_alert_event(
    session: AsyncSession,
    watch_id: int,
) -> AlertEvent | None:
    result = await session.execute(
        select(AlertEvent)
        .where(AlertEvent.watch_id == watch_id)
        .order_by(AlertEvent.sent_at.desc(), AlertEvent.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def count_alerted_watchers(
    session: AsyncSession,
    *,
    within_days: int = 30,
) -> int:
    """North Star proxy: пользователи с ≥1 алертом за окно."""
    since = datetime.now(timezone.utc) - timedelta(days=max(1, within_days))
    result = await session.execute(
        select(func.count(func.distinct(AlertEvent.user_id))).where(
            AlertEvent.sent_at >= since
        )
    )
    return int(result.scalar_one() or 0)


# --- TG-04 watch sharing ---


class ShareCloneResult:
    """Результат подтверждения share."""

    __slots__ = ("watch", "created_new", "is_owner", "invalid")

    def __init__(
        self,
        *,
        watch: Watch | None = None,
        created_new: bool = False,
        is_owner: bool = False,
        invalid: bool = False,
    ) -> None:
        self.watch = watch
        self.created_new = created_new
        self.is_owner = is_owner
        self.invalid = invalid


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def get_watch_for_user(
    session: AsyncSession,
    *,
    watch_id: int,
    user_id: int,
) -> Watch | None:
    result = await session.execute(
        select(Watch).where(
            Watch.id == watch_id,
            Watch.user_id == user_id,
            Watch.is_active.is_(True),
        )
    )
    return result.scalar_one_or_none()


async def create_watch_share_token(
    session: AsyncSession,
    *,
    watch_id: int,
    owner_user_id: int,
    expires_at: datetime,
    max_uses: int,
    now: datetime | None = None,
    max_active: int = 10,
) -> tuple["WatchShareToken", str]:
    from flypingavia.bot.share_tokens import (
        MAX_ACTIVE_SHARES_PER_WATCH,
        generate_share_token,
        hash_share_token,
    )
    from flypingavia.db.models import WatchShareToken

    limit = max_active if max_active > 0 else MAX_ACTIVE_SHARES_PER_WATCH
    watch = await get_watch_for_user(session, watch_id=watch_id, user_id=owner_user_id)
    if watch is None:
        raise LookupError("watch_not_found")

    now_utc = _aware_utc(now or datetime.now(timezone.utc))
    expires_at = _aware_utc(expires_at)

    active = list(
        (
            await session.execute(
                select(WatchShareToken)
                .where(
                    WatchShareToken.watch_id == watch_id,
                    WatchShareToken.owner_user_id == owner_user_id,
                    WatchShareToken.revoked_at.is_(None),
                    WatchShareToken.expires_at > now_utc,
                )
                .order_by(WatchShareToken.created_at.asc(), WatchShareToken.id.asc())
            )
        ).scalars().all()
    )
    while len(active) >= limit:
        oldest = active.pop(0)
        oldest.revoked_at = now_utc

    raw = generate_share_token()
    row = WatchShareToken(
        token_hash=hash_share_token(raw),
        watch_id=watch_id,
        owner_user_id=owner_user_id,
        expires_at=expires_at,
        used_count=0,
        max_uses=max_uses,
        created_at=now_utc,
    )
    session.add(row)
    await session.flush()
    return row, raw


def _share_is_valid(share: "WatchShareToken", *, now: datetime) -> bool:
    now_utc = _aware_utc(now)
    if share.revoked_at is not None:
        return False
    if _aware_utc(share.expires_at) <= now_utc:
        return False
    if share.used_count >= share.max_uses:
        return False
    return True


async def get_valid_watch_share(
    session: AsyncSession,
    *,
    raw_token: str,
    now: datetime,
) -> "WatchShareToken | None":
    from flypingavia.bot.share_tokens import hash_share_token
    from flypingavia.db.models import WatchShareToken
    from sqlalchemy.orm import selectinload

    token_hash = hash_share_token(raw_token)
    result = await session.execute(
        select(WatchShareToken)
        .options(selectinload(WatchShareToken.watch))
        .where(WatchShareToken.token_hash == token_hash)
    )
    share = result.scalar_one_or_none()
    if share is None:
        return None
    if not _share_is_valid(share, now=now):
        return None
    watch = share.watch
    if watch is None or not watch.is_active:
        return None
    return share


async def get_share_by_id(
    session: AsyncSession,
    *,
    share_id: int,
    now: datetime,
) -> "WatchShareToken | None":
    from flypingavia.db.models import WatchShareToken
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(WatchShareToken)
        .options(selectinload(WatchShareToken.watch))
        .where(WatchShareToken.id == share_id)
    )
    share = result.scalar_one_or_none()
    if share is None:
        return None
    if not _share_is_valid(share, now=now):
        return None
    if share.watch is None or not share.watch.is_active:
        return None
    return share


async def clone_watch_from_verified_share(
    session: AsyncSession,
    *,
    share_id: int,
    recipient_user_id: int,
    now: datetime,
) -> ShareCloneResult:
    """Клонировать Watch по share_id после HMAC proof (handler/service).

    Не вызывать из публичного callback с «голым» share_id без verify_share_callback_proof.
    """
    from flypingavia.db.models import WatchShareRedemption, WatchShareToken
    from sqlalchemy.exc import IntegrityError

    now_utc = _aware_utc(now)
    share = await get_share_by_id(session, share_id=share_id, now=now_utc)
    if share is None:
        return ShareCloneResult(invalid=True)

    if share.owner_user_id == recipient_user_id:
        return ShareCloneResult(watch=share.watch, is_owner=True)

    existing = await session.execute(
        select(WatchShareRedemption).where(
            WatchShareRedemption.share_token_id == share.id,
            WatchShareRedemption.recipient_user_id == recipient_user_id,
        )
    )
    redemption = existing.scalar_one_or_none()
    if redemption is not None:
        watch = await session.get(Watch, redemption.created_watch_id)
        return ShareCloneResult(watch=watch, created_new=False)

    # Re-check uses under lock of transaction
    await session.refresh(share)
    if not _share_is_valid(share, now=now_utc):
        return ShareCloneResult(invalid=True)

    src = share.watch
    assert src is not None
    recipient = await session.get(User, recipient_user_id)
    if recipient is None:
        return ShareCloneResult(invalid=True)

    from sqlalchemy import update

    nested = await session.begin_nested()
    try:
        # Атомарный инкремент used_count с защитой от race поверх max_uses.
        bumped = await session.execute(
            update(WatchShareToken)
            .where(
                WatchShareToken.id == share.id,
                WatchShareToken.revoked_at.is_(None),
                WatchShareToken.used_count < WatchShareToken.max_uses,
            )
            .values(used_count=WatchShareToken.used_count + 1)
            .execution_options(synchronize_session=False)
        )
        if bumped.rowcount != 1:
            await nested.rollback()
            return ShareCloneResult(invalid=True)

        new_watch = await add_watch(
            session,
            user=recipient,
            origin=src.origin,
            destination=src.destination,
            origin_name=src.origin_name,
            destination_name=src.destination_name,
            origin_search=src.origin_search,
            destination_search=src.destination_search,
            max_price=src.max_price,
            depart_date=src.depart_date,
            return_date=src.return_date,
            adults=src.adults or 1,
            children=src.children or 0,
            infants=src.infants or 0,
            currency=src.currency,
            flexibility_days=int(getattr(src, "flexibility_days", 0) or 0),
        )
        row = WatchShareRedemption(
            share_token_id=share.id,
            recipient_user_id=recipient_user_id,
            created_watch_id=new_watch.id,
            redeemed_at=now_utc,
        )
        session.add(row)
        await session.flush()
        await nested.commit()
        await session.refresh(share)
        return ShareCloneResult(watch=new_watch, created_new=True)
    except IntegrityError:
        await nested.rollback()
        existing2 = await session.execute(
            select(WatchShareRedemption).where(
                WatchShareRedemption.share_token_id == share.id,
                WatchShareRedemption.recipient_user_id == recipient_user_id,
            )
        )
        redemption2 = existing2.scalar_one_or_none()
        if redemption2 is None:
            return ShareCloneResult(invalid=True)
        watch = await session.get(Watch, redemption2.created_watch_id)
        return ShareCloneResult(watch=watch, created_new=False)


async def revoke_watch_share(
    session: AsyncSession,
    *,
    share_id: int,
    owner_user_id: int,
    now: datetime,
) -> bool:
    from flypingavia.db.models import WatchShareToken

    share = await session.get(WatchShareToken, share_id)
    if share is None or share.owner_user_id != owner_user_id:
        return False
    if share.revoked_at is not None:
        return True
    share.revoked_at = _aware_utc(now)
    await session.flush()
    return True


async def revoke_all_watch_shares(
    session: AsyncSession,
    *,
    watch_id: int,
    owner_user_id: int,
    now: datetime,
) -> int:
    from flypingavia.db.models import WatchShareToken

    watch = await get_watch_for_user(session, watch_id=watch_id, user_id=owner_user_id)
    if watch is None:
        return 0
    now_utc = _aware_utc(now)
    result = await session.execute(
        select(WatchShareToken).where(
            WatchShareToken.watch_id == watch_id,
            WatchShareToken.owner_user_id == owner_user_id,
            WatchShareToken.revoked_at.is_(None),
        )
    )
    rows = list(result.scalars().all())
    for row in rows:
        row.revoked_at = now_utc
    await session.flush()
    return len(rows)
