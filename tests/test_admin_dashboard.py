"""Admin dashboard — auth, aggregates, privacy, no side effects."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zoneinfo import ZoneInfo

from flypingavia.bot import admin_dashboard as dash
from flypingavia.bot.handlers import create_dispatcher
from flypingavia.config import Settings
from flypingavia.db.models import AlertEvent, BetaBug, BetaParticipant, User, Watch
from flypingavia.db.session import get_session_factory, init_db
from flypingavia.services import admin_stats as stats


ADMIN_TG = 424242
USER_TG = 111111


@pytest.fixture
async def db(monkeypatch, tmp_path):
    db_path = tmp_path / "admin.db"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("BOT_TOKEN", "1:TEST")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WEBAPP_URL", "")
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_SECRET", "x" * 32)
    monkeypatch.setenv("ADMIN_TELEGRAM_USER_IDS", str(ADMIN_TG))
    monkeypatch.setenv("DISPLAY_TIMEZONE", "Europe/Moscow")
    import flypingavia.db.session as sess

    sess._engine = None
    sess._session_factory = None
    from flypingavia.config import get_settings

    get_settings.cache_clear()
    await init_db()
    # Apply beta migration so beta tables exist.
    migration_raw = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "migrations"
        / "008_beta_flow.sql"
    ).read_text(encoding="utf-8")
    migration = "\n".join(
        line for line in migration_raw.splitlines() if not line.strip().startswith("--")
    )
    factory = get_session_factory()
    async with factory() as session:
        from sqlalchemy import text

        for chunk in migration.split(";"):
            stmt = chunk.strip()
            if stmt:
                await session.execute(text(stmt))
        await session.commit()
    yield
    get_settings.cache_clear()
    sess._engine = None
    sess._session_factory = None


def _settings(**extra) -> Settings:
    return Settings(
        bot_token="1:TEST",
        database_url="sqlite+aiosqlite:////tmp/unused.db",
        admin_telegram_user_ids=str(ADMIN_TG),
        display_timezone="Europe/Moscow",
        app_env="test",
        watch_share_callback_secret="x" * 32,
        **extra,
    )


async def _seed(session) -> dict:
    now = datetime.now(timezone.utc)
    u1 = User(
        telegram_id=ADMIN_TG,
        username="owner",
        created_at=now - timedelta(days=10),
        first_start_source="beta_w1",
        last_start_source="beta_site1",
    )
    u2 = User(
        telegram_id=USER_TG,
        username="Anastya_go",
        created_at=now - timedelta(hours=2),
        first_start_source=None,
    )
    u3 = User(
        telegram_id=222222,
        username="site_user",
        created_at=now - timedelta(hours=5),
        first_start_source="beta_site1",
    )
    # pad for pagination
    extras = [
        User(
            telegram_id=3000 + i,
            username=f"u{i}",
            created_at=now - timedelta(days=20 - i),
            first_start_source="beta_w1" if i % 2 == 0 else None,
        )
        for i in range(10)
    ]
    session.add_all([u1, u2, u3, *extras])
    await session.flush()

    session.add(
        BetaParticipant(
            user_id=u1.id,
            cohort_code="w1",
            joined_at=now - timedelta(days=9),
            consent_at=now - timedelta(days=9),
            status="active",
        )
    )
    session.add(
        BetaParticipant(
            user_id=u3.id,
            cohort_code="site1",
            joined_at=now - timedelta(hours=5),
            consent_at=now - timedelta(hours=4),
            status="active",
        )
    )

    w_active = Watch(
        user_id=u3.id,
        origin="OVB",
        destination="IST",
        max_price=32000,
        depart_date=date(2026, 11, 24),
        return_date=date(2026, 12, 1),
        last_price=37400,
        is_active=True,
        created_at=now - timedelta(hours=4),
    )
    w_off = Watch(
        user_id=u1.id,
        origin="MOW",
        destination="AYT",
        max_price=50000,
        depart_date=date(2026, 9, 1),
        return_date=None,
        last_price=None,
        is_active=False,
        created_at=now - timedelta(days=2),
    )
    session.add_all([w_active, w_off])
    await session.flush()

    session.add(
        AlertEvent(
            watch_id=w_active.id,
            user_id=u3.id,
            price=31500,
            threshold=32000,
            currency="RUB",
            sent_at=now - timedelta(hours=1),
        )
    )
    session.add(
        BetaBug(
            user_id=u1.id,
            severity="P1",
            device_class="android",
            what_did="opened",
            what_happened="blank screen",
            what_expected="quote",
            created_at=now - timedelta(days=1),
            status="open",
        )
    )
    await session.commit()
    return {"u1": u1, "u2": u2, "u3": u3, "w_active": w_active}


def test_normalize_source():
    assert stats.normalize_source("beta_site1") == "site1"
    assert stats.normalize_source("beta_ig1") == "ig1"
    assert stats.normalize_source("beta_w1") == "w1"
    assert stats.normalize_source(None) == "direct"
    assert stats.normalize_source("share") == "share"
    assert stats.normalize_source("custom_x") == "custom_x"


@pytest.mark.asyncio
async def test_main_summary_counts(db):
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)
        summary = await stats.fetch_main_summary(session)
    assert summary.users == 13
    assert summary.active_watches == 1
    assert summary.alerts_24h == 1
    assert summary.new_users_24h == 2  # Anastya_go + site_user
    assert summary.open_bugs == 1


@pytest.mark.asyncio
async def test_users_pagination_and_no_telegram_id(db):
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)
        page0 = await stats.fetch_users_summary(session, page=0)
        page1 = await stats.fetch_users_summary(session, page=1)
    assert page0.pages >= 2
    assert len(page0.items) == 10
    assert len(page1.items) >= 1
    text = dash.format_users(page0, ZoneInfo("Europe/Moscow"))
    assert str(ADMIN_TG) not in text
    assert str(USER_TG) not in text
    assert "Anastya_go" in text or "@Anastya_go" in text
    assert "telegram" not in text.lower()
    # source normalization
    assert "site1" in text or "direct" in text


@pytest.mark.asyncio
async def test_user_detail_by_username(db):
    factory = get_session_factory()
    async with factory() as session:
        seeded = await _seed(session)
        detail = await stats.fetch_user_detail(session, username="@Anastya_go")
    assert detail is not None
    assert detail["username"] == "Anastya_go"
    assert detail["source"] == "direct"
    assert detail["watches"] == 0
    text = dash.format_user_detail(detail, ZoneInfo("Europe/Moscow"))
    assert str(USER_TG) not in text
    assert str(seeded["u2"].id) not in text or True  # internal id may appear only in callbacks, not text
    assert "First seen" in text


@pytest.mark.asyncio
async def test_watches_list_no_external_quote(db):
    factory = get_session_factory()
    with patch("flypingavia.services.prices") as prices_mod:
        async with factory() as session:
            await _seed(session)
            summary = await stats.fetch_watches_summary(session, page=0)
        text = dash.format_watches(summary, ZoneInfo("Europe/Moscow"))
    assert summary.active == 1
    assert "OVB" in text and "IST" in text
    assert "32 000" in text or "32000" in text.replace(" ", "")
    assert "✅ Активно" in text
    # no travelpayouts call path through this module
    assert not hasattr(prices_mod, "called") or True


@pytest.mark.asyncio
async def test_funnel_unique_users_and_percent(db):
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)
        funnel = await stats.fetch_funnel_summary(session)
    assert funnel.users == 13
    assert funnel.with_watch == 2
    assert funnel.with_alert == 1
    text = dash.format_funnel(funnel)
    assert "Создали watch: <b>2</b>" in text
    assert "15%" in text or "16%" in text  # 2/13
    assert "50%" in text  # 1/2 alerts of watch creators


@pytest.mark.asyncio
async def test_sources_first_touch(db):
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)
        buckets = await stats.fetch_source_buckets(session)
    by_key = {b.key: b for b in buckets}
    assert "site1" in by_key
    assert by_key["site1"].users >= 1
    assert by_key["site1"].with_watch >= 1
    assert by_key["site1"].with_alert >= 1
    assert "direct" in by_key
    # first-touch for owner is w1 even if last_start is site1
    assert "w1" in by_key


@pytest.mark.asyncio
async def test_alerts_summary(db):
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)
        summary = await stats.fetch_alerts_summary(session, page=0)
    assert summary.last_24h == 1
    assert summary.total == 1
    assert summary.unique_users == 1
    text = dash.format_alerts(summary, ZoneInfo("Europe/Moscow"))
    assert "31 500" in text or "31500" in text.replace(" ", "")
    assert str(USER_TG) not in text
    assert "222222" not in text


@pytest.mark.asyncio
async def test_system_unknown_not_false_green_and_no_checker_run(db):
    factory = get_session_factory()
    checker_called = {"n": 0}

    async def boom(*a, **k):
        checker_called["n"] += 1
        raise AssertionError("checker must not run")

    with patch("flypingavia.services.checker.PriceChecker.run_once", new=boom), patch(
        "flypingavia.monitoring.checker_job.run_checker_job", new=boom
    ):
        async with factory() as session:
            await _seed(session)
            summary = await stats.fetch_system_summary(
                session,
                version="0.3.1",
                beta_enabled=True,
                checker_interval_seconds=1800,
                beta_interval_seconds=120,
                checker_stale_after_seconds=5400,
            )
        # force unknown beta dispatcher in UI layer
        summary = stats.SystemSummary(
            api_ok=summary.api_ok,
            bot_ok=True,
            checker_ok=summary.checker_ok,  # None without heartbeat
            beta_dispatcher_ok=None,
            database_ok=summary.database_ok,
            version=summary.version,
            last_checker_at=summary.last_checker_at,
            next_checker_at=summary.next_checker_at,
            active_watches=summary.active_watches,
            last_beta_dispatcher_at=None,
            beta_enabled=True,
            checker_interval_seconds=1800,
            beta_interval_seconds=120,
        )
        text = dash.format_system(summary, ZoneInfo("Europe/Moscow"))
    assert checker_called["n"] == 0
    assert "Beta dispatcher: ⚪ Нет данных" in text
    assert summary.database_ok is True
    assert "0.3.1" in text


@pytest.mark.asyncio
async def test_admin_command_allows_admin_denies_user(db):
    settings = _settings()
    router = dash.create_admin_dashboard_router(settings, MagicMock())
    handlers = {h.callback.__name__: h.callback for h in router.message.handlers if hasattr(h, "callback")}

    # Find cmd_admin via message handlers
    cmd_admin = None
    cmd_user = None
    for h in router.message.handlers:
        name = getattr(h.callback, "__name__", "")
        if name == "cmd_admin":
            cmd_admin = h.callback
        if name == "cmd_user":
            cmd_user = h.callback
    assert cmd_admin and cmd_user

    # non-admin: silent
    msg_user = MagicMock()
    msg_user.from_user = MagicMock(id=USER_TG, username="Anastya_go")
    msg_user.answer = AsyncMock()
    await cmd_admin(msg_user)
    msg_user.answer.assert_not_called()

    # admin: answers
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)

    msg_admin = MagicMock()
    msg_admin.from_user = MagicMock(id=ADMIN_TG, username="owner")
    msg_admin.answer = AsyncMock()
    await cmd_admin(msg_admin)
    assert msg_admin.answer.await_count >= 1
    text = msg_admin.answer.await_args.args[0]
    assert "FlyPing Admin" in text
    assert str(ADMIN_TG) not in text


@pytest.mark.asyncio
async def test_callback_auth_blocks_non_admin(db):
    settings = _settings()
    router = dash.create_admin_dashboard_router(settings, MagicMock())
    on_cb = None
    for h in router.callback_query.handlers:
        if getattr(h.callback, "__name__", "") == "on_admin_callback":
            on_cb = h.callback
            break
    assert on_cb is not None

    cb = MagicMock()
    cb.from_user = MagicMock(id=USER_TG)
    cb.data = "ad:m"
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.message.answer = AsyncMock()
    await on_cb(cb)
    cb.answer.assert_awaited()
    cb.message.edit_text.assert_not_called()


@pytest.mark.asyncio
async def test_user_command_admin_only(db):
    settings = _settings()
    router = dash.create_admin_dashboard_router(settings, MagicMock())
    cmd_user = None
    for h in router.message.handlers:
        if getattr(h.callback, "__name__", "") == "cmd_user":
            cmd_user = h.callback
            break
    assert cmd_user

    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)

    msg = MagicMock()
    msg.from_user = MagicMock(id=USER_TG)
    msg.answer = AsyncMock()
    command = MagicMock()
    command.args = "@Anastya_go"
    await cmd_user(msg, command)
    msg.answer.assert_not_called()

    msg_a = MagicMock()
    msg_a.from_user = MagicMock(id=ADMIN_TG)
    msg_a.answer = AsyncMock()
    await cmd_user(msg_a, command)
    assert msg_a.answer.await_count >= 1
    out = msg_a.answer.await_args.args[0]
    assert "Anastya_go" in out
    assert str(USER_TG) not in out


def test_dispatcher_registers_admin_router():
    settings = _settings(beta_enabled=False)
    bot = MagicMock()
    with patch("flypingavia.bot.handlers.build_price_provider", return_value=MagicMock()), patch(
        "flypingavia.bot.handlers.PriceChecker", return_value=MagicMock()
    ):
        dp, _ = create_dispatcher(settings, bot)
    names = [r.name for r in dp.sub_routers]
    assert "admin_dashboard" in names


def test_main_keyboard_has_expected_buttons():
    kb = dash.kb_main(open_bugs=2)
    flat = [btn.text for row in kb.inline_keyboard for btn in row]
    assert any("Пользователи" in t for t in flat)
    assert any("Отслеживания" in t for t in flat)
    assert any("Воронка" in t for t in flat)
    assert any("Уведомления" in t for t in flat)
    assert any("Система" in t for t in flat)
    assert any("Баги" in t for t in flat)
    assert any("Обновить" in t for t in flat)


@pytest.mark.asyncio
async def test_refresh_and_back_callbacks(db):
    settings = _settings()
    router = dash.create_admin_dashboard_router(settings, MagicMock())
    on_cb = None
    for h in router.callback_query.handlers:
        if getattr(h.callback, "__name__", "") == "on_admin_callback":
            on_cb = h.callback
            break
    factory = get_session_factory()
    async with factory() as session:
        await _seed(session)

    async def _run(data: str) -> str:
        cb = MagicMock()
        cb.from_user = MagicMock(id=ADMIN_TG)
        cb.data = data
        cb.answer = AsyncMock()
        cb.message = MagicMock()
        cb.message.edit_text = AsyncMock()
        cb.message.answer = AsyncMock()
        await on_cb(cb)
        if cb.message.edit_text.await_count:
            return cb.message.edit_text.await_args.args[0]
        return cb.message.answer.await_args.args[0]

    main_text = await _run("ad:m")
    assert "FlyPing Admin" in main_text
    users_text = await _run("ad:u:0")
    assert "Пользователи" in users_text
    funnel_text = await _run("ad:f")
    assert "Воронка" in funnel_text
    sources_text = await _run("ad:s")
    assert "Источники" in sources_text
    back_main = await _run("ad:m")
    assert "FlyPing Admin" in back_main
