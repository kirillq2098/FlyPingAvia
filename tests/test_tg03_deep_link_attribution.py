"""TG-03: deep-link start payload attribution."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject

from flypingavia.bot.start_payload import (
    build_telegram_start_link,
    normalize_start_payload,
)
from flypingavia.config import get_settings
from flypingavia.db import repository as repo
from flypingavia.db.session import init_db, session_scope
import flypingavia.db.session as db_session


ROOT = Path(__file__).resolve().parents[1]
T0 = datetime(2026, 7, 30, 10, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 30, 14, 0, 0, tzinfo=timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- normalization ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("site", "site"),
        ("instagram_2026", "instagram_2026"),
        ("partner-blog", "partner-blog"),
        ("share_AbC123", "share_AbC123"),
        ("a" * 64, "a" * 64),
        ("a" * 65, None),
        ("hello world", None),
        ("сайт", None),
        ("a/b", None),
        ("src?x=1", None),
        ("<script>", None),
        ("line\nbreak", None),
        ("../../etc/passwd", None),
    ],
)
def test_normalize_start_payload(raw, expected) -> None:
    assert normalize_start_payload(raw) == expected


def test_normalize_preserves_case() -> None:
    assert normalize_start_payload("Campaign_X") == "Campaign_X"


# --- link builder ---


def test_build_link_with_payload() -> None:
    url = build_telegram_start_link(bot_username="FlyPingBot", payload="site")
    assert url == "https://t.me/FlyPingBot?start=site"


def test_build_link_without_payload() -> None:
    assert build_telegram_start_link(bot_username="FlyPingBot") == "https://t.me/FlyPingBot"
    assert build_telegram_start_link(bot_username="FlyPingBot", payload=None) == "https://t.me/FlyPingBot"
    assert build_telegram_start_link(bot_username="FlyPingBot", payload="") == "https://t.me/FlyPingBot"


def test_build_link_strips_at() -> None:
    url = build_telegram_start_link(bot_username="@FlyPingBot", payload="site")
    assert url == "https://t.me/FlyPingBot?start=site"


def test_build_link_invalid_username() -> None:
    with pytest.raises(ValueError):
        build_telegram_start_link(bot_username="ab")
    with pytest.raises(ValueError):
        build_telegram_start_link(bot_username="bad name")


def test_build_link_invalid_payload() -> None:
    with pytest.raises(ValueError):
        build_telegram_start_link(bot_username="FlyPingBot", payload="bad payload")


def test_build_link_urlencode_underscore_ok() -> None:
    url = build_telegram_start_link(bot_username="FlyPingBot", payload="share_AbC123")
    assert "start=share_AbC123" in url
    assert "token" not in url.lower()
    assert url.startswith("https://t.me/")


# --- repository ---


@pytest.fixture
async def tg03_db(tmp_path, monkeypatch):
    db_path = tmp_path / "tg03.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    get_settings.cache_clear()
    db_session._engine = None
    db_session._session_factory = None
    await init_db()
    yield
    if db_session._engine is not None:
        await db_session._engine.dispose()
    db_session._engine = None
    db_session._session_factory = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_record_start_no_source(tg03_db) -> None:
    async with session_scope() as session:
        user = await repo.record_user_start(
            session,
            telegram_user_id=1001,
            source=None,
            started_at=T0,
            username="u1",
        )
        assert user.telegram_id == 1001
        assert user.username == "u1"
        assert user.first_start_source is None
        assert user.last_start_source is None
        assert user.first_start_at == T0
        assert user.last_start_at == T0


@pytest.mark.asyncio
async def test_record_first_valid_source(tg03_db) -> None:
    async with session_scope() as session:
        user = await repo.record_user_start(
            session, telegram_user_id=1002, source="site", started_at=T0
        )
        assert user.first_start_source == "site"
        assert user.last_start_source == "site"
        assert user.first_start_at == T0
        assert user.last_start_at == T0


@pytest.mark.asyncio
async def test_first_touch_preserved_last_updates(tg03_db) -> None:
    async with session_scope() as session:
        await repo.record_user_start(
            session, telegram_user_id=1003, source="site", started_at=T0
        )
    async with session_scope() as session:
        user = await repo.record_user_start(
            session, telegram_user_id=1003, source="instagram", started_at=T1
        )
        assert user.first_start_source == "site"
        assert user.last_start_source == "instagram"
        assert _aware(user.first_start_at) == T0
        assert _aware(user.last_start_at) == T1


@pytest.mark.asyncio
async def test_start_without_source_keeps_last(tg03_db) -> None:
    async with session_scope() as session:
        await repo.record_user_start(
            session, telegram_user_id=1004, source="site", started_at=T0
        )
    async with session_scope() as session:
        user = await repo.record_user_start(
            session, telegram_user_id=1004, source=None, started_at=T1
        )
        assert user.first_start_source == "site"
        assert user.last_start_source == "site"
        assert _aware(user.first_start_at) == T0
        assert _aware(user.last_start_at) == T1


@pytest.mark.asyncio
async def test_wa03_user_then_first_start(tg03_db) -> None:
    async with session_scope() as session:
        await repo.get_or_create_user(session, telegram_id=2001, username="mini")
    async with session_scope() as session:
        user = await repo.record_user_start(
            session, telegram_user_id=2001, source="telegram_post", started_at=T0
        )
        assert user.username == "mini"
        assert user.first_start_source == "telegram_post"
        assert user.first_start_at == T0
        assert user.last_start_at == T0


@pytest.mark.asyncio
async def test_no_duplicate_users(tg03_db) -> None:
    async with session_scope() as session:
        await repo.record_user_start(
            session, telegram_user_id=3001, source="site", started_at=T0, username="a"
        )
    async with session_scope() as session:
        await repo.record_user_start(
            session, telegram_user_id=3001, source="instagram", started_at=T1, username="b"
        )
        from sqlalchemy import select, func
        from flypingavia.db.models import User

        n = await session.scalar(select(func.count()).select_from(User).where(User.telegram_id == 3001))
        assert n == 1
        user = await session.scalar(select(User).where(User.telegram_id == 3001))
        assert user.username == "b"
        assert user.first_start_source == "site"
        assert user.last_start_source == "instagram"


@pytest.mark.asyncio
async def test_sqlite_migration_adds_user_columns(tg03_db) -> None:
    from sqlalchemy import text

    async with session_scope() as session:
        rows = (await session.execute(text("PRAGMA table_info(users)"))).fetchall()
    names = {r[1] for r in rows}
    assert {"first_start_source", "last_start_source", "first_start_at", "last_start_at"} <= names


# --- handler ---


@pytest.mark.asyncio
async def test_cmd_start_saves_payload_and_keeps_tg02(tg03_db, monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.services.checker import PriceChecker
    from flypingavia.config import Settings

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        webapp_url="",
    )
    provider = MagicMock()
    checker = MagicMock(spec=PriceChecker)
    router = create_router(settings, checker, provider)

    # find cmd_start
    cmd_start = None
    for observer in router.message.handlers:
        if observer.callback.__name__ == "cmd_start":
            cmd_start = observer.callback
            break
    assert cmd_start is not None

    answers: list[str] = []

    message = MagicMock()
    message.from_user = MagicMock(id=9001, username="srcuser", first_name="Кирилл")
    message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text) or MagicMock())

    state = AsyncMock()
    command = CommandObject(command="start", args="site")

    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )

    await cmd_start(message, state, command)

    state.clear.assert_awaited()
    assert any("сторож цены" in a for a in answers)
    assert not any("site" in a for a in answers if "сторож" in a or "Привет" in a)
    # no watch create on start
    joined = "\n".join(answers)
    assert "Подписка #" not in joined

    async with session_scope() as session:
        from sqlalchemy import select
        from flypingavia.db.models import User

        user = await session.scalar(select(User).where(User.telegram_id == 9001))
        assert user is not None
        assert user.first_start_source == "site"
        assert user.last_start_source == "site"


@pytest.mark.asyncio
async def test_cmd_start_invalid_payload_ok(tg03_db, monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.config import Settings

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
    )
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = next(
        o.callback for o in router.message.handlers if o.callback.__name__ == "cmd_start"
    )

    answers: list[str] = []
    message = MagicMock()
    message.from_user = MagicMock(id=9002, username="u", first_name="A")
    message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    state = AsyncMock()
    command = CommandObject(command="start", args="bad payload")
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )
    await cmd_start(message, state, command)
    assert any("сторож цены" in a for a in answers)
    async with session_scope() as session:
        from sqlalchemy import select
        from flypingavia.db.models import User

        user = await session.scalar(select(User).where(User.telegram_id == 9002))
        assert user.first_start_source is None


@pytest.mark.asyncio
async def test_cmd_start_first_last_touch(tg03_db, monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.config import Settings

    settings = Settings(
        bot_token="1:T", app_env="test", webapp_dev_user_id=0, travelpayouts_token=""
    )
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = next(
        o.callback for o in router.message.handlers if o.callback.__name__ == "cmd_start"
    )
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )

    async def _run(args: str | None):
        message = MagicMock()
        message.from_user = MagicMock(id=9003, username="u", first_name="B")
        message.answer = AsyncMock()
        await cmd_start(message, AsyncMock(), CommandObject(command="start", args=args))

    await _run("site")
    await _run("instagram")
    await _run(None)

    async with session_scope() as session:
        from sqlalchemy import select
        from flypingavia.db.models import User

        user = await session.scalar(select(User).where(User.telegram_id == 9003))
        assert user.first_start_source == "site"
        assert user.last_start_source == "instagram"


def test_docs_and_backlog() -> None:
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")
    chunk = backlog.split("### TG-03")[1].split("### TG-04")[0]
    assert "**Статус:** Done" in chunk
    attr = (ROOT / "docs/ATTRIBUTION.md").read_text(encoding="utf-8")
    assert "first_start_source" in attr
    assert "TG-04" in attr
    assert "не реализован" in attr.lower() or "не внедр" in attr.lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "?start=" in readme
    assert "64" in readme
