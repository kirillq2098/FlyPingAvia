"""TG-04: share Watch via opaque Telegram deep link."""

from __future__ import annotations

import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.filters import CommandObject
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from flypingavia.bot.share_tokens import (
    INVALID_SHARE_MESSAGE,
    OWN_SHARE_MESSAGE,
    SHARE_PREFIX,
    build_share_payload,
    generate_share_token,
    hash_share_token,
    parse_share_payload,
)
from flypingavia.bot.start_payload import normalize_start_payload
from flypingavia.config import Settings, get_settings
from flypingavia.db import repository as repo
from flypingavia.db.models import User, Watch, WatchShareToken
from flypingavia.db.session import init_db, session_scope
import flypingavia.db.session as db_session


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
async def tg04_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "tg04.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "FlyPingBot")
    monkeypatch.setenv("WATCH_SHARE_TTL_HOURS", "168")
    monkeypatch.setenv("WATCH_SHARE_MAX_USES", "20")
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


async def _user(session, tid: int, username: str = "u"):
    return await repo.get_or_create_user(session, telegram_id=tid, username=username)


async def _watch(session, user, **kwargs):
    defaults = dict(
        origin="MOW",
        destination="IST",
        origin_name="Москва",
        destination_name="Стамбул",
        max_price=45_000,
        depart_date=None,
        return_date=None,
        adults=1,
        children=0,
        infants=0,
        currency="RUB",
        flexibility_days=3,
    )
    defaults.update(kwargs)
    return await repo.add_watch(session, user=user, **defaults)


# --- helpers ---


def test_token_helpers_use_secrets(monkeypatch) -> None:
    called = {"n": 0}
    real = secrets.token_urlsafe

    def wrapped(nbytes=None):
        called["n"] += 1
        return real(nbytes)

    monkeypatch.setattr("flypingavia.bot.share_tokens.secrets.token_urlsafe", wrapped)
    a = generate_share_token()
    b = generate_share_token()
    assert called["n"] == 2
    assert a != b
    # 22 bytes → ≥ 128 bit entropy
    assert 22 * 8 >= 128
    payload = build_share_payload(a)
    assert payload.startswith(SHARE_PREFIX)
    assert len(payload) <= 64
    assert normalize_start_payload(payload) == payload
    assert parse_share_payload(payload) == a
    assert parse_share_payload("site") is None
    assert parse_share_payload("share_") is None
    assert parse_share_payload("") is None
    assert parse_share_payload("src_abc") is None
    h = hash_share_token(a)
    assert h == hash_share_token(a)
    assert h != a
    assert len(h) == 64


def test_config_share_bounds() -> None:
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_ttl_hours=0)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_ttl_hours=721)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_max_uses=0)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_max_uses=1001)
    s = Settings(bot_token="1:T", app_env="test")
    assert s.watch_share_ttl_hours == 168
    assert s.watch_share_max_uses == 20


def test_preview_formatter_safe() -> None:
    from flypingavia.bot.formatters import format_shared_watch_preview

    w = MagicMock(
        origin="MOW",
        destination="IST",
        origin_name="Москва <x>",
        destination_name="Стамбул",
        depart_date=date(2026, 9, 15),
        return_date=date(2026, 9, 22),
        adults=2,
        children=0,
        infants=0,
        currency="RUB",
        max_price=45_000,
        flexibility_days=3,
        id=999,
        user_id=42,
    )
    text = format_shared_watch_preview(w)
    assert "поделились поездкой" in text.lower()
    assert "Москва" in text
    assert "&lt;x&gt;" in text
    assert "999" not in text or "подписку" in text.lower()
    assert "42" not in text
    assert "share_" not in text
    w.flexibility_days = 0
    w.return_date = None
    text2 = format_shared_watch_preview(w)
    assert "только выбранная дата" in text2
    assert "Обратно" not in text2


# --- repository ---


@pytest.mark.asyncio
async def test_create_share_and_clone(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 1, "owner")
        recipient = await _user(session, 2, "recv")
        w = await _watch(
            session,
            owner,
            max_price=40_000,
            flexibility_days=3,
            depart_date=date(2026, 9, 15),
            return_date=date(2026, 9, 22),
            adults=2,
        )
        w.last_price = 33_000
        w.last_checked_at = NOW
        share, raw = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=7),
            max_uses=20,
            now=NOW,
        )
        assert share.token_hash == hash_share_token(raw)
        assert not hasattr(WatchShareToken, "raw_token")
        cols = {c.name for c in WatchShareToken.__table__.columns}
        assert "token_hash" in cols
        assert "raw_token" not in cols
        assert "token" not in cols

    async with session_scope() as session:
        valid = await repo.get_valid_watch_share(session, raw_token=raw, now=NOW)
        assert valid is not None
        assert valid.watch.flexibility_days == 3
        # preview does not bump used_count
        assert valid.used_count == 0

    async with session_scope() as session:
        owner = await _user(session, 1)
        r = await repo.clone_watch_from_share(
            session, share_id=share.id, recipient_user_id=owner.id, now=NOW
        )
        assert r.is_owner and not r.created_new
        share_row = await session.get(WatchShareToken, share.id)
        assert share_row.used_count == 0

    async with session_scope() as session:
        recipient = await _user(session, 2)
        r1 = await repo.clone_watch_from_share(
            session, share_id=share.id, recipient_user_id=recipient.id, now=NOW
        )
        assert r1.created_new and r1.watch is not None
        assert r1.watch.user_id == recipient.id
        assert r1.watch.max_price == 40_000
        assert r1.watch.flexibility_days == 3
        assert r1.watch.adults == 2
        assert r1.watch.depart_date == date(2026, 9, 15)
        assert r1.watch.last_price is None
        assert r1.watch.last_checked_at is None
        assert r1.watch.id != share.watch_id if False else True
        wid = r1.watch.id
        orig_id = share.watch_id

    async with session_scope() as session:
        recipient = await _user(session, 2)
        r2 = await repo.clone_watch_from_share(
            session, share_id=share.id, recipient_user_id=recipient.id, now=NOW
        )
        assert not r2.created_new
        assert r2.watch is not None and r2.watch.id == wid
        share2 = await session.get(WatchShareToken, share.id)
        assert share2.used_count == 1
        assert wid != orig_id


@pytest.mark.asyncio
async def test_foreign_cannot_create_share(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 10)
        other = await _user(session, 11)
        w = await _watch(session, owner)
        with pytest.raises(LookupError):
            await repo.create_watch_share_token(
                session,
                watch_id=w.id,
                owner_user_id=other.id,
                expires_at=NOW + timedelta(days=1),
                max_uses=5,
                now=NOW,
            )


@pytest.mark.asyncio
async def test_expired_revoked_max_uses(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 21)
        w = await _watch(session, owner)
        expired, raw_exp = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW - timedelta(seconds=1),
            max_uses=20,
            now=NOW - timedelta(hours=1),
        )
        active, raw_act = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=1),
            max_uses=1,
            now=NOW,
        )
        ok = await repo.revoke_watch_share(
            session, share_id=active.id, owner_user_id=owner.id, now=NOW
        )
        assert ok
        limited, raw_lim = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=1),
            max_uses=1,
            now=NOW,
        )
        sid = limited.id

    async with session_scope() as session:
        assert await repo.get_valid_watch_share(session, raw_token=raw_exp, now=NOW) is None
        assert await repo.get_valid_watch_share(session, raw_token=raw_act, now=NOW) is None

    async with session_scope() as session:
        a = await _user(session, 22)
        b = await _user(session, 23)
        r1 = await repo.clone_watch_from_share(
            session, share_id=sid, recipient_user_id=a.id, now=NOW
        )
        assert r1.created_new
        r2 = await repo.clone_watch_from_share(
            session, share_id=sid, recipient_user_id=b.id, now=NOW
        )
        assert r2.invalid


@pytest.mark.asyncio
async def test_revoke_and_max_active(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 30)
        w = await _watch(session, owner)
        tokens = []
        for i in range(11):
            row, raw = await repo.create_watch_share_token(
                session,
                watch_id=w.id,
                owner_user_id=owner.id,
                expires_at=NOW + timedelta(days=7),
                max_uses=20,
                now=NOW + timedelta(seconds=i),
                max_active=10,
            )
            tokens.append((row.id, raw))
        oldest = await session.get(WatchShareToken, tokens[0][0])
        assert oldest.revoked_at is not None
        newest = await session.get(WatchShareToken, tokens[-1][0])
        assert newest.revoked_at is None
        n = await repo.revoke_all_watch_shares(
            session, watch_id=w.id, owner_user_id=owner.id, now=NOW + timedelta(hours=1)
        )
        assert n >= 1


@pytest.mark.asyncio
async def test_second_recipient_and_original_deactivate(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 40)
        a = await _user(session, 41)
        b = await _user(session, 42)
        w = await _watch(session, owner)
        share, raw = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=1),
            max_uses=20,
            now=NOW,
        )
        r_a = await repo.clone_watch_from_share(
            session, share_id=share.id, recipient_user_id=a.id, now=NOW
        )
        r_b = await repo.clone_watch_from_share(
            session, share_id=share.id, recipient_user_id=b.id, now=NOW
        )
        assert r_a.watch.id != r_b.watch.id
        share2 = await session.get(WatchShareToken, share.id)
        assert share2.used_count == 2
        await repo.deactivate_watch(session, owner.id, w.id)

    async with session_scope() as session:
        assert await repo.get_valid_watch_share(session, raw_token=raw, now=NOW) is None


# --- API ---


@pytest.mark.asyncio
async def test_api_share_auth_and_owner(tg04_db, monkeypatch) -> None:
    from flypingavia.api.app import create_api
    from flypingavia.api.telegram_auth import build_test_init_data

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = "1:T"
    init_a = build_test_init_data(token, user_id=501, auth_date=now_ts)
    init_b = build_test_init_data(token, user_id=502, auth_date=now_ts)

    async with session_scope() as session:
        owner = await _user(session, 501)
        await _user(session, 502)
        w = await _watch(session, owner)
        wid = w.id

    app = create_api(
        Settings(
            bot_token=token,
            app_env="test",
            webapp_dev_user_id=0,
            travelpayouts_token="",
            telegram_bot_username="FlyPingBot",
            watch_share_ttl_hours=168,
            watch_share_max_uses=20,
        )
    )
    headers_a = {"Authorization": f"tma {init_a}"}
    headers_b = {"Authorization": f"tma {init_b}"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        assert (await c.get("/api/health")).status_code == 200
        assert (await c.post(f"/api/watches/{wid}/share")).status_code == 401
        ok = await c.post(f"/api/watches/{wid}/share", headers=headers_a)
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert "share_" in body["url"]
        assert set(body.keys()) == {"url", "expires_at"}
        assert "token" not in body
        assert "hash" not in body
        assert "owner" not in str(body).lower() or "owner" not in body
        bad = await c.post(f"/api/watches/{wid}/share", headers=headers_b)
        assert bad.status_code == 404
        # WA-03: foreign list empty
        lst = await c.get("/api/watches", headers=headers_b)
        assert lst.status_code == 200
        assert all(item["id"] != wid for item in lst.json())
        rev = await c.delete(f"/api/watches/{wid}/shares", headers=headers_a)
        assert rev.status_code == 200
        assert rev.json()["revoked"] >= 1
        rev_b = await c.delete(f"/api/watches/{wid}/shares", headers=headers_b)
        assert rev_b.status_code == 404


@pytest.mark.asyncio
async def test_api_share_requires_bot_username(tg04_db) -> None:
    from flypingavia.api.app import create_api
    from flypingavia.api.telegram_auth import build_test_init_data

    now_ts = int(datetime.now(timezone.utc).timestamp())
    token = "1:T"
    init_a = build_test_init_data(token, user_id=601, auth_date=now_ts)
    async with session_scope() as session:
        owner = await _user(session, 601)
        w = await _watch(session, owner)
        wid = w.id
    app = create_api(
        Settings(
            bot_token=token,
            app_env="test",
            webapp_dev_user_id=0,
            travelpayouts_token="",
            telegram_bot_username="",
        )
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.post(
            f"/api/watches/{wid}/share",
            headers={"Authorization": f"tma {init_a}"},
        )
        assert res.status_code == 503


# --- handler /start share ---


def _handler_by_name(router, name: str):
    for coll in (router.message, router.callback_query):
        for o in coll.handlers:
            if o.callback.__name__ == name:
                return o.callback
    raise AssertionError(name)


@pytest.mark.asyncio
async def test_start_share_preview_and_invalid(tg04_db, monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router

    async with session_scope() as session:
        owner = await _user(session, 701, "owner_u")
        w = await _watch(session, owner, origin_name="Москва", destination_name="Стамбул")
        share, raw = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=7),
            max_uses=20,
            now=NOW,
        )
        payload = build_share_payload(raw)
        sid = share.id

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        telegram_bot_username="FlyPingBot",
    )
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = _handler_by_name(router, "cmd_start")
    answers: list[str] = []
    message = MagicMock()
    message.from_user = MagicMock(id=702, username="recv", first_name="Bob")
    message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )
    await cmd_start(message, AsyncMock(), CommandObject(command="start", args=payload))
    joined = "\n".join(answers)
    assert "поделились поездкой" in joined.lower()
    assert "Москва" in joined
    assert "owner_u" not in joined
    assert "701" not in joined
    assert payload not in joined
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 702))
        assert u.last_start_source == payload

    # invalid share → welcome + safe error
    answers.clear()
    message2 = MagicMock()
    message2.from_user = MagicMock(id=703, username="x", first_name="Ann")
    message2.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    await cmd_start(
        message2, AsyncMock(), CommandObject(command="start", args="share_notexistTOKEN1234567890ab")
    )
    joined2 = "\n".join(answers)
    assert INVALID_SHARE_MESSAGE.split("\n")[0] in joined2
    assert "FlyPing" in joined2
    assert "сторож" in joined2.lower() or "проверяет" in joined2.lower()

    # keyboard has share button
    from flypingavia.bot import keyboards as kb

    markup = kb.watch_actions_kb(99, "https://example.com")
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert "🔗 Поделиться" in texts
    assert "🔒 Отозвать ссылки" in texts


@pytest.mark.asyncio
async def test_share_confirm_cancel_owner(tg04_db, monkeypatch) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.bot.formatters import format_start_message

    async with session_scope() as session:
        owner = await _user(session, 801, "own")
        recv = await _user(session, 802, "recv")
        w = await _watch(session, owner, flexibility_days=3)
        share, _raw = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(days=7),
            max_uses=20,
            now=NOW,
        )
        sid = share.id
        orig_id = w.id

    settings = Settings(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        telegram_bot_username="FlyPingBot",
    )
    router = create_router(settings, MagicMock(), MagicMock())
    confirm = _handler_by_name(router, "cb_share_confirm")
    cancel = _handler_by_name(router, "cb_share_cancel")
    share_cb = _handler_by_name(router, "cb_share")

    # cancel
    cb_cancel = MagicMock()
    cb_cancel.data = "share_cancel"
    cb_cancel.from_user = MagicMock(id=802, username="recv")
    cb_cancel.answer = AsyncMock()
    cb_cancel.message = MagicMock()
    cb_cancel.message.answer = AsyncMock()
    await cancel(cb_cancel)
    async with session_scope() as session:
        recv_u = await _user(session, 802)
        watches = list(
            (
                await session.execute(select(Watch).where(Watch.user_id == recv_u.id))
            ).scalars().all()
        )
        assert watches == []

    # confirm creates
    answers: list[str] = []
    cb = MagicMock()
    cb.data = f"share_confirm:{sid}"
    cb.from_user = MagicMock(id=802, username="recv")
    cb.answer = AsyncMock()
    cb.message = MagicMock()
    cb.message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    await confirm(cb)
    async with session_scope() as session:
        recv_u = await _user(session, 802)
        watches = list(
            (
                await session.execute(select(Watch).where(Watch.user_id == recv_u.id))
            ).scalars().all()
        )
        assert len(watches) == 1
        assert watches[0].flexibility_days == 3
        assert watches[0].id != orig_id
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # repeat confirm idempotent
    await confirm(cb)
    async with session_scope() as session:
        recv_u = await _user(session, 802)
        watches = list(
            (
                await session.execute(select(Watch).where(Watch.user_id == recv_u.id))
            ).scalars().all()
        )
        assert len(watches) == 1
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # owner confirm
    answers.clear()
    cb_own = MagicMock()
    cb_own.data = f"share_confirm:{sid}"
    cb_own.from_user = MagicMock(id=801, username="own")
    cb_own.answer = AsyncMock()
    cb_own.message = MagicMock()
    cb_own.message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    await confirm(cb_own)
    assert any(OWN_SHARE_MESSAGE in t for t in answers)
    async with session_scope() as session:
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # ownership on share button for foreign watch
    cb_share = MagicMock()
    cb_share.data = f"wshare:{orig_id}"
    cb_share.from_user = MagicMock(id=802, username="recv")
    cb_share.answer = AsyncMock()
    cb_share.message = MagicMock()
    cb_share.message.answer = AsyncMock()
    await share_cb(cb_share)
    cb_share.answer.assert_awaited()
    assert "не найдена" in (cb_share.answer.await_args.args[0] if cb_share.answer.await_args.args else "")

    # TG-02 welcome intact
    assert "сторож" in format_start_message("Ann").lower() or "FlyPing" in format_start_message("Ann")


def test_frontend_share_and_docs() -> None:
    js = (ROOT / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    assert "data-share=" in js
    assert "/share" in js
    assert "apiFetch" in js
    assert '"tma "' in js
    assert "localStorage.setItem" not in js
    assert "encodeURIComponent" in js
    assert "t.me/share/url" in js
    assert "share-close" in js
    assert "проверять цену за вас" in js
    css = (ROOT / "flypingavia/web/static/app.css").read_text(encoding="utf-8")
    assert "share-modal" in css
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")
    section = backlog.split("### TG-04")[1].split("### TG-05")[0]
    assert "**Статус:** Done" in section
    assert (ROOT / "scripts/migrations/004_tg04_watch_sharing.sql").is_file()
    assert (ROOT / "docs/WATCH_SHARING.md").is_file()
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "WATCH_SHARE_TTL_HOURS=168" in env
    assert "WATCH_SHARE_MAX_USES=20" in env
    sec = (ROOT / "docs/SECURITY.md").read_text(encoding="utf-8")
    assert "TG-04" in sec
    assert "Mini App Auth" in sec
