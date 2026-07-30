from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from flypingavia.config import get_settings
from flypingavia.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

_SQLITE_WATCH_EXTRA_COLUMNS = {
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

_SQLITE_USER_EXTRA_COLUMNS = {
    "first_start_source": "VARCHAR(64)",
    "last_start_source": "VARCHAR(64)",
    "first_start_at": "DATETIME",
    "last_start_at": "DATETIME",
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


async def _migrate_sqlite_table(conn, table: str, columns: dict[str, str]) -> None:
    result = await conn.execute(text(f"PRAGMA table_info({table})"))
    existing = {row[1] for row in result.fetchall()}
    for column, col_type in columns.items():
        if column not in existing:
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


async def _migrate_sqlite(conn) -> None:
    await _migrate_sqlite_table(conn, "watches", _SQLITE_WATCH_EXTRA_COLUMNS)
    await _migrate_sqlite_table(conn, "users", _SQLITE_USER_EXTRA_COLUMNS)


async def init_db() -> None:
    """Создаёт таблицы и догоняет колонки на SQLite.

    Явные SQL-миграции:
    - scripts/migrations/001_alert_events.sql
    - scripts/migrations/002_watch_flexibility_days.sql
    - scripts/migrations/003_tg03_user_start_attribution.sql
    - scripts/migrations/004_tg04_watch_sharing.sql
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
