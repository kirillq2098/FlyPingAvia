from __future__ import annotations

from datetime import date
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from flypingavia.db.models import User, Watch


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
) -> Watch:
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
