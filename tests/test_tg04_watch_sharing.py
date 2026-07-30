"""TG-04: share Watch via opaque Telegram deep link + secure confirm proof."""

from __future__ import annotations

import hmac
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.filters import CommandObject
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from flypingavia.bot.share_tokens import (
    ATTRIBUTION_SHARE_SOURCE,
    INVALID_SHARE_MESSAGE,
    OWN_SHARE_MESSAGE,
    SHARE_PREFIX,
    attribution_source_for_start_payload,
    build_share_payload,
    create_share_callback_proof,
    generate_share_token,
    hash_share_token,
    parse_share_payload,
    verify_share_callback_proof,
)
from flypingavia.bot.start_payload import normalize_start_payload
from flypingavia.config import Settings, get_settings
from flypingavia.db import repository as repo
from flypingavia.db.models import User, Watch, WatchShareRedemption, WatchShareToken
from flypingavia.db.session import init_db, session_scope
import flypingavia.db.session as db_session


ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 7, 30, 12, 0, 0, tzinfo=timezone.utc)
SECRET = "test-watch-share-callback-secret-32chars!!"


@pytest.fixture
async def tg04_db(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_PATH", str(tmp_path / "tg04.db"))
    monkeypatch.setenv("BOT_TOKEN", "1:T")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WEBAPP_DEV_USER_ID", "0")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "FlyPingBot")
    monkeypatch.setenv("WATCH_SHARE_TTL_HOURS", "168")
    monkeypatch.setenv("WATCH_SHARE_MAX_USES", "20")
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_SECRET", SECRET)
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_TTL_SECONDS", "900")
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


def _settings(**kwargs) -> Settings:
    base = dict(
        bot_token="1:T",
        app_env="test",
        webapp_dev_user_id=0,
        travelpayouts_token="",
        telegram_bot_username="FlyPingBot",
        watch_share_ttl_hours=168,
        watch_share_max_uses=20,
        watch_share_callback_secret=SECRET,
        watch_share_callback_ttl_seconds=900,
    )
    base.update(kwargs)
    return Settings(**base)


def _handler_by_name(router, name: str):
    for coll in (router.message, router.callback_query):
        for o in coll.handlers:
            if o.callback.__name__ == name:
                return o.callback
    raise AssertionError(name)


def _proof(share_id: int, tid: int, *, exp: datetime | None = None, now: datetime | None = None) -> str:
    base = now or datetime.now(timezone.utc)
    return create_share_callback_proof(
        share_id=share_id,
        telegram_user_id=tid,
        expires_at=exp or (base + timedelta(seconds=900)),
        secret=SECRET,
    )


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
    assert 22 * 8 >= 128
    payload = build_share_payload(a)
    assert payload.startswith(SHARE_PREFIX)
    assert len(payload) <= 64
    assert normalize_start_payload(payload) == payload
    assert parse_share_payload(payload) == a
    assert parse_share_payload("site") is None
    assert parse_share_payload("share_") is None
    assert parse_share_payload("") is None
    h = hash_share_token(a)
    assert h == hash_share_token(a)
    assert h != a
    assert len(h) == 64


def test_attribution_source_helper() -> None:
    assert attribution_source_for_start_payload(None) is None
    assert attribution_source_for_start_payload("site") == "site"
    assert attribution_source_for_start_payload("instagram") == "instagram"
    raw = generate_share_token()
    payload = build_share_payload(raw)
    assert attribution_source_for_start_payload(payload) == ATTRIBUTION_SHARE_SOURCE
    assert attribution_source_for_start_payload(payload) == "share"
    assert raw not in (attribution_source_for_start_payload(payload) or "")


def test_config_share_bounds(monkeypatch) -> None:
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_ttl_hours=0)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_ttl_hours=721)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_max_uses=0)
    with pytest.raises(Exception):
        Settings(bot_token="1:T", app_env="test", watch_share_callback_ttl_seconds=30)
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_SECRET", "")
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(Exception):
        Settings(
            bot_token="1:T",
            app_env="production",
            webapp_dev_user_id=0,
            webapp_url="https://app.example.com",
            watch_share_callback_secret="",
            _env_file=None,
        )
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("WATCH_SHARE_CALLBACK_SECRET", SECRET)
    s = Settings(bot_token="1:T", app_env="test")
    assert s.watch_share_ttl_hours == 168
    assert s.watch_share_max_uses == 20
    assert len(s.watch_share_callback_secret) >= 32
    assert s.watch_share_callback_ttl_seconds == 900


def test_callback_proof_unit() -> None:
    now = datetime.now(timezone.utc)
    proof = _proof(42, 1001, now=now)
    assert len(proof.encode("utf-8")) <= 64
    assert proof.startswith("sc:")
    assert SECRET not in proof
    assert "share_" not in proof
    assert verify_share_callback_proof(
        proof, telegram_user_id=1001, secret=SECRET, now=now
    ) == 42
    assert (
        verify_share_callback_proof(
            proof, telegram_user_id=9999, secret=SECRET, now=now
        )
        is None
    )
    # tamper share id in payload text
    parts = proof.split(":")
    tampered = f"sc:43:{parts[2]}:{parts[3]}"
    assert (
        verify_share_callback_proof(
            tampered, telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    # tamper exp
    tampered_exp = f"sc:42:{int(parts[2]) + 10}:{parts[3]}"
    assert (
        verify_share_callback_proof(
            tampered_exp, telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    # tamper sig
    bad_sig = proof[:-1] + ("A" if proof[-1] != "A" else "B")
    assert (
        verify_share_callback_proof(
            bad_sig, telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    expired = _proof(42, 1001, exp=now - timedelta(seconds=1))
    assert (
        verify_share_callback_proof(
            expired, telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    assert (
        verify_share_callback_proof("", telegram_user_id=1001, secret=SECRET, now=now)
        is None
    )
    assert (
        verify_share_callback_proof(
            "not-a-proof", telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    assert (
        verify_share_callback_proof(
            "share_confirm:42", telegram_user_id=1001, secret=SECRET, now=now
        )
        is None
    )
    # compare_digest is used (monkeypatch)
    called = {"n": 0}
    real = hmac.compare_digest

    def wrapped(a, b):
        called["n"] += 1
        return real(a, b)

    import flypingavia.bot.share_tokens as st

    st.hmac.compare_digest = wrapped
    try:
        verify_share_callback_proof(
            proof, telegram_user_id=1001, secret=SECRET, now=now
        )
        assert called["n"] >= 1
    finally:
        st.hmac.compare_digest = real


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
    assert "&lt;x&gt;" in text
    assert "42" not in text
    assert "share_" not in text


# --- repository ---


@pytest.mark.asyncio
async def test_create_share_and_clone(tg04_db) -> None:
    async with session_scope() as session:
        owner = await _user(session, 1, "owner")
        await _user(session, 2, "recv")
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
        cols = {c.name for c in WatchShareToken.__table__.columns}
        assert "raw_token" not in cols
        orig_id = w.id
        sid = share.id

    async with session_scope() as session:
        valid = await repo.get_valid_watch_share(session, raw_token=raw, now=NOW)
        assert valid is not None
        assert valid.used_count == 0

    async with session_scope() as session:
        owner = await _user(session, 1)
        r = await repo.clone_watch_from_verified_share(
            session, share_id=sid, recipient_user_id=owner.id, now=NOW
        )
        assert r.is_owner and not r.created_new

    async with session_scope() as session:
        recipient = await _user(session, 2)
        r1 = await repo.clone_watch_from_verified_share(
            session, share_id=sid, recipient_user_id=recipient.id, now=NOW
        )
        assert r1.created_new and r1.watch is not None
        assert r1.watch.user_id == recipient.id
        assert r1.watch.max_price == 40_000
        assert r1.watch.flexibility_days == 3
        assert r1.watch.last_price is None
        wid = r1.watch.id

    async with session_scope() as session:
        recipient = await _user(session, 2)
        r2 = await repo.clone_watch_from_verified_share(
            session, share_id=sid, recipient_user_id=recipient.id, now=NOW
        )
        assert not r2.created_new
        assert r2.watch is not None and r2.watch.id == wid
        share2 = await session.get(WatchShareToken, sid)
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
        _expired, raw_exp = await repo.create_watch_share_token(
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
        assert await repo.revoke_watch_share(
            session, share_id=active.id, owner_user_id=owner.id, now=NOW
        )
        limited, _raw_lim = await repo.create_watch_share_token(
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
        r1 = await repo.clone_watch_from_verified_share(
            session, share_id=sid, recipient_user_id=a.id, now=NOW
        )
        assert r1.created_new
        r2 = await repo.clone_watch_from_verified_share(
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
            row, _raw = await repo.create_watch_share_token(
                session,
                watch_id=w.id,
                owner_user_id=owner.id,
                expires_at=NOW + timedelta(days=7),
                max_uses=20,
                now=NOW + timedelta(seconds=i),
                max_active=10,
            )
            tokens.append(row.id)
        oldest = await session.get(WatchShareToken, tokens[0])
        assert oldest.revoked_at is not None
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
        r_a = await repo.clone_watch_from_verified_share(
            session, share_id=share.id, recipient_user_id=a.id, now=NOW
        )
        r_b = await repo.clone_watch_from_verified_share(
            session, share_id=share.id, recipient_user_id=b.id, now=NOW
        )
        assert r_a.watch.id != r_b.watch.id
        await repo.deactivate_watch(session, owner.id, w.id)

    async with session_scope() as session:
        assert await repo.get_valid_watch_share(session, raw_token=raw, now=NOW) is None


# --- API ---


@pytest.mark.asyncio
async def test_api_share_auth_and_owner(tg04_db) -> None:
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

    app = create_api(_settings(bot_token=token))
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
        bad = await c.post(f"/api/watches/{wid}/share", headers=headers_b)
        assert bad.status_code == 404
        rev = await c.delete(f"/api/watches/{wid}/shares", headers=headers_a)
        assert rev.json()["revoked"] >= 1
        assert (await c.delete(f"/api/watches/{wid}/shares", headers=headers_b)).status_code == 404


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
    app = create_api(_settings(bot_token=token, telegram_bot_username=""))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        res = await c.post(
            f"/api/watches/{wid}/share",
            headers={"Authorization": f"tma {init_a}"},
        )
        assert res.status_code == 503


# --- handlers ---


@pytest.mark.asyncio
async def test_start_attribution_share_and_sources(tg04_db, monkeypatch) -> None:
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

    settings = _settings()
    router = create_router(settings, MagicMock(), MagicMock())
    cmd_start = _handler_by_name(router, "cmd_start")
    monkeypatch.setattr(
        "flypingavia.bot.handlers.get_location_directory",
        lambda: MagicMock(ensure_loaded=AsyncMock()),
    )

    async def run_start(tid: int, args: str | None, name: str = "U") -> list[str]:
        answers: list[str] = []
        message = MagicMock()
        message.from_user = MagicMock(id=tid, username=f"u{tid}", first_name=name)
        message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
        await cmd_start(message, AsyncMock(), CommandObject(command="start", args=args))
        return answers

    # ordinary sources
    await run_start(710, "site")
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 710))
        assert u.first_start_source == "site"
        assert u.last_start_source == "site"

    await run_start(711, "instagram")
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 711))
        assert u.last_start_source == "instagram"

    # valid share → attribution "share", no raw token
    answers = await run_start(702, payload, "Bob")
    joined = "\n".join(answers)
    assert "поделились поездкой" in joined.lower()
    assert "Москва" in joined
    assert "owner_u" not in joined
    assert raw not in joined
    assert payload not in joined
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 702))
        assert u.first_start_source == "share"
        assert u.last_start_source == "share"
        assert raw not in (u.first_start_source or "")
        assert raw not in (u.last_start_source or "")
        assert payload not in (u.first_start_source or "")
        # DB text columns must not contain raw token
        rows = (
            await session.execute(
                text(
                    "SELECT first_start_source, last_start_source, username FROM users"
                )
            )
        ).all()
        blob = " ".join(str(c) for row in rows for c in row)
        assert raw not in blob
        assert payload not in blob

    # second share updates last to share again; then ordinary source
    await run_start(702, payload)
    await run_start(702, "partner_blog")
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 702))
        assert u.first_start_source == "share"
        assert u.last_start_source == "partner_blog"

    # invalid share payload format still whitelist → attribution share (no secret stored)
    bad = "share_notexistTOKEN1234567890ab"
    await run_start(703, bad)
    async with session_scope() as session:
        u = await session.scalar(select(User).where(User.telegram_id == 703))
        assert u.last_start_source == "share"
        assert bad not in (u.last_start_source or "")
        assert "notexistTOKEN" not in (u.last_start_source or "")

    # keyboard share buttons
    from flypingavia.bot import keyboards as kb

    markup = kb.watch_actions_kb(99, "https://example.com")
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert "🔗 Поделиться" in texts

    # preview keyboard contains proof not bare id
    proof = _proof(sid, 702)
    mk = kb.share_confirm_kb(proof)
    data = mk.inline_keyboard[0][0].callback_data
    assert data.startswith("sc:")
    assert f"share_confirm:{sid}" != data


@pytest.mark.asyncio
async def test_share_confirm_attacks_and_happy_path(tg04_db) -> None:
    from flypingavia.bot.handlers import create_router
    from flypingavia.bot.formatters import format_start_message

    async with session_scope() as session:
        owner = await _user(session, 801, "own")
        await _user(session, 802, "recv")
        await _user(session, 803, "attacker")
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

    settings = _settings()
    router = create_router(settings, MagicMock(), MagicMock())
    confirm = _handler_by_name(router, "cb_share_confirm")
    legacy = _handler_by_name(router, "cb_share_confirm_legacy")
    cancel = _handler_by_name(router, "cb_share_cancel")

    async def call_confirm(tid: int, data: str) -> list[str]:
        answers: list[str] = []
        cb = MagicMock()
        cb.data = data
        cb.from_user = MagicMock(id=tid, username=f"u{tid}")
        cb.answer = AsyncMock()
        cb.message = MagicMock()
        cb.message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
        if data.startswith("share_confirm:"):
            await legacy(cb)
        else:
            await confirm(cb)
        return answers

    # cancel
    cb_cancel = MagicMock()
    cb_cancel.data = "share_cancel"
    cb_cancel.from_user = MagicMock(id=802, username="recv")
    cb_cancel.answer = AsyncMock()
    cb_cancel.message = MagicMock()
    cb_cancel.message.answer = AsyncMock()
    await cancel(cb_cancel)

    # attacker: bare share_confirm:<id>
    answers = await call_confirm(803, f"share_confirm:{sid}")
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)
    async with session_scope() as session:
        attacker = await _user(session, 803)
        n = len(
            list(
                (
                    await session.execute(select(Watch).where(Watch.user_id == attacker.id))
                ).scalars().all()
            )
        )
        assert n == 0
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 0
        red = await session.scalar(
            select(WatchShareRedemption).where(
                WatchShareRedemption.share_token_id == sid,
                WatchShareRedemption.recipient_user_id == attacker.id,
            )
        )
        assert red is None

    # attacker: forged proof for wrong user / tampered share id
    proof_recv = _proof(sid, 802)
    answers = await call_confirm(803, proof_recv)
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)
    proof_other = _proof(sid + 1, 802)
    answers = await call_confirm(802, proof_other)
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)

    # expired proof
    expired = _proof(sid, 802, exp=NOW - timedelta(seconds=5))
    answers = await call_confirm(802, expired)
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)

    # happy path with valid proof
    answers = await call_confirm(802, proof_recv)
    async with session_scope() as session:
        recv = await _user(session, 802)
        watches = list(
            (await session.execute(select(Watch).where(Watch.user_id == recv.id))).scalars().all()
        )
        assert len(watches) == 1
        assert watches[0].flexibility_days == 3
        assert watches[0].id != orig_id
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # idempotent
    await call_confirm(802, proof_recv)
    async with session_scope() as session:
        recv = await _user(session, 802)
        watches = list(
            (await session.execute(select(Watch).where(Watch.user_id == recv.id))).scalars().all()
        )
        assert len(watches) == 1
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # owner proof → no clone
    answers = await call_confirm(801, _proof(sid, 801))
    assert any(OWN_SHARE_MESSAGE in t for t in answers)
    async with session_scope() as session:
        share_row = await session.get(WatchShareToken, sid)
        assert share_row.used_count == 1

    # revoke then confirm
    async with session_scope() as session:
        owner = await _user(session, 801)
        await repo.revoke_all_watch_shares(
            session, watch_id=orig_id, owner_user_id=owner.id, now=NOW
        )
    answers = await call_confirm(803, _proof(sid, 803))
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)

    assert "FlyPing" in format_start_message("Ann")


@pytest.mark.asyncio
async def test_expired_share_after_preview_no_clone(tg04_db) -> None:
    from flypingavia.bot.handlers import create_router

    async with session_scope() as session:
        owner = await _user(session, 901)
        await _user(session, 902)
        w = await _watch(session, owner)
        share, _raw = await repo.create_watch_share_token(
            session,
            watch_id=w.id,
            owner_user_id=owner.id,
            expires_at=NOW + timedelta(hours=1),
            max_uses=20,
            now=NOW,
        )
        sid = share.id

    settings = _settings()
    router = create_router(settings, MagicMock(), MagicMock())
    confirm = _handler_by_name(router, "cb_share_confirm")
    proof = _proof(sid, 902)

    # expire the share token itself
    async with session_scope() as session:
        row = await session.get(WatchShareToken, sid)
        row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)

    cb = MagicMock()
    cb.data = proof
    cb.from_user = MagicMock(id=902, username="r")
    cb.answer = AsyncMock()
    answers: list[str] = []
    cb.message = MagicMock()
    cb.message.answer = AsyncMock(side_effect=lambda text, **kw: answers.append(text))
    await confirm(cb)
    assert any(INVALID_SHARE_MESSAGE.split("\n")[0] in t for t in answers)
    async with session_scope() as session:
        recv = await _user(session, 902)
        watches = list(
            (await session.execute(select(Watch).where(Watch.user_id == recv.id))).scalars().all()
        )
        assert watches == []


def test_frontend_share_and_docs() -> None:
    js = (ROOT / "flypingavia/web/static/app.js").read_text(encoding="utf-8")
    assert "data-share=" in js
    assert "apiFetch" in js
    assert "localStorage.setItem" not in js
    assert "t.me/share/url" in js
    backlog = (ROOT / "docs/FEATURE_BACKLOG.md").read_text(encoding="utf-8")
    section = backlog.split("### TG-04")[1].split("### TG-05")[0]
    assert "**Статус:** Done" in section
    watch_doc = (ROOT / "docs/WATCH_SHARING.md").read_text(encoding="utf-8")
    assert 'только как `share`' in watch_doc or 'только `"share"`' in watch_doc or 'только как' in watch_doc
    assert "HMAC" in watch_doc
    assert "полный payload `share_" not in watch_doc
    attr = (ROOT / "docs/ATTRIBUTION.md").read_text(encoding="utf-8")
    assert 'только как' in attr and "`share`" in attr
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "WATCH_SHARE_CALLBACK_SECRET" in env
    assert "WATCH_SHARE_CALLBACK_TTL_SECONDS=900" in env
    sec = (ROOT / "docs/SECURITY.md").read_text(encoding="utf-8")
    assert "raw token не сохраняется" in sec.lower() or "raw token **не** хранится" in sec
