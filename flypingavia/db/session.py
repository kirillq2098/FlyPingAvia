from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flypingavia.config import get_settings
from flypingavia.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

_SQLITE_EXTRA_COLUMNS = {
    "origin_name": "VARCHAR(128)",
    "destination_name": "VARCHAR(128)",
    "origin_search": "TEXT",
    "destination_search": "TEXT",
    "last_origin_airport": "VARCHAR(3)",
    "last_destination_airport": "VARCHAR(3)",
    "return_date": "DATE",
    "adults": "INTEGER DEFAULT 1",
    "children": "INTEGER DEFAULT 0",
    "infants": "INTEGER DEFAULT 0",
    "flexibility_days": "INTEGER DEFAULT 0 NOT NULL",
}


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=False)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


async def _migrate_sqlite(conn) -> None:
    result = await conn.execute(text("PRAGMA table_info(watches)"))
    existing = {row[1] for row in result.fetchall()}
    for column, col_type in _SQLITE_EXTRA_COLUMNS.items():
        if column not in existing:
            await conn.execute(text(f"ALTER TABLE watches ADD COLUMN {column} {col_type}"))


async def init_db() -> None:
    """Создаёт таблицы (в т.ч. alert_events) и догоняет колонки watches на SQLite.

    Явные SQL-миграции:
    - scripts/migrations/001_alert_events.sql
    - scripts/migrations/002_watch_flexibility_days.sql
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if engine.dialect.name == "sqlite":
            await _migrate_sqlite(conn)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
