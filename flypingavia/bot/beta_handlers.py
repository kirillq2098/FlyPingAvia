"""Closed Beta Phase A: consent, survey callbacks, /bug, admin commands."""

from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from flypingavia.bot import keyboards as kb
from flypingavia.config import Settings
from flypingavia.db import repository as repo
from flypingavia.db.session import session_scope
from flypingavia.services import beta_repo as beta

logger = logging.getLogger(__name__)


class BugReport(StatesGroup):
    did = State()
    happened = State()
    expected = State()
    device = State()
    device_note = State()
    screenshot = State()
    severity = State()


class SurveyFreeText(StatesGroup):
    waiting = State()


def _is_admin(message: Message, settings: Settings) -> bool:
    user = message.from_user
    return user is not None and user.id in settings.admin_user_id_set


def create_beta_router(settings: Settings, bot: Bot) -> Router:
    router = Router(name="beta")

    @router.callback_query(F.data == "beta:consent")
    async def on_consent(callback: CallbackQuery) -> None:
        user = callback.from_user
        if user is None:
            await callback.answer()
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            ok = await beta.set_consent(session, user_id=db_user.id)
        await callback.answer("Спасибо!" if ok else "Ок")
        if callback.message:
            await callback.message.answer(
                "Отлично. Создайте первую подписку — после этого может прийти короткий опрос.",
                reply_markup=kb.main_menu(settings.telegram_webapp_url),
            )

    @router.message(Command("beta_stop"))
    async def cmd_beta_stop(message: Message, state: FSMContext) -> None:
        await state.clear()
        user = message.from_user
        if user is None:
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            ok = await beta.set_opt_out(session, user_id=db_user.id)
        if ok:
            await message.answer(
                "Вы отписались от beta-сообщений и опросов. "
                "Уведомления о ценах по подпискам продолжат приходить.",
                reply_markup=kb.main_menu(settings.telegram_webapp_url),
            )
        else:
            await message.answer(
                "Вы не в списке участников беты. Если нужно — напишите владельцу.",
                reply_markup=kb.main_menu(settings.telegram_webapp_url),
            )

    @router.callback_query(F.data.startswith("beta:survey:result:"))
    async def survey_result(callback: CallbackQuery) -> None:
        user = callback.from_user
        if user is None or not callback.data:
            await callback.answer()
            return
        result = callback.data.rsplit(":", 1)[-1]
        mapping = {"yes": "yes", "partial": "partial", "no": "no"}
        if result not in mapping:
            await callback.answer()
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            survey = await beta.apply_survey_result(
                session, user_id=db_user.id, result=mapping[result]
            )
            if survey is None or survey.status == "completed":
                await callback.answer("Уже сохранено")
                return
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "2) Насколько понятен сервис? (1 — совсем нет, 5 — всё ясно)",
                reply_markup=kb.beta_survey_clarity_kb(),
            )

    @router.callback_query(F.data.startswith("beta:survey:clarity:"))
    async def survey_clarity(callback: CallbackQuery, state: FSMContext) -> None:
        user = callback.from_user
        if user is None or not callback.data:
            await callback.answer()
            return
        try:
            score = int(callback.data.rsplit(":", 1)[-1])
        except ValueError:
            await callback.answer()
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            survey = await beta.apply_survey_result(
                session, user_id=db_user.id, clarity_score=score
            )
            if survey is None or survey.status == "completed":
                await callback.answer("Уже сохранено")
                return
        await state.set_state(SurveyFreeText.waiting)
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "3) Что было непонятно? Напишите текстом или нажмите «Пропустить».",
                reply_markup=kb.beta_survey_free_kb(),
            )

    @router.callback_query(SurveyFreeText.waiting, F.data == "beta:survey:skip_text")
    @router.callback_query(F.data == "beta:survey:skip_text")
    async def survey_skip_text(callback: CallbackQuery, state: FSMContext) -> None:
        user = callback.from_user
        if user is None:
            await callback.answer()
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            await beta.apply_survey_result(
                session, user_id=db_user.id, free_text="", complete=True
            )
        await state.clear()
        await callback.answer()
        if callback.message:
            await callback.message.answer("Спасибо! Ответ сохранён.")

    @router.message(SurveyFreeText.waiting, F.text)
    async def survey_free_text(message: Message, state: FSMContext) -> None:
        user = message.from_user
        if user is None:
            return
        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            await beta.apply_survey_result(
                session,
                user_id=db_user.id,
                free_text=message.text or "",
                complete=True,
            )
        await state.clear()
        await message.answer("Спасибо! Ответ сохранён.")

    @router.message(Command("bug"))
    async def cmd_bug(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(BugReport.did)
        await message.answer(
            "Сообщение о проблеме.\n\n1) Что вы делали?",
            reply_markup=kb.cancel_kb(),
        )

    @router.message(BugReport.did, F.text)
    async def bug_did(message: Message, state: FSMContext) -> None:
        if message.text and message.text.strip() == "❌ Отмена":
            await state.clear()
            await message.answer("Отменил.", reply_markup=kb.main_menu())
            return
        await state.update_data(what_did=beta.clip_text(message.text))
        await state.set_state(BugReport.happened)
        await message.answer("2) Что произошло?")

    @router.message(BugReport.happened, F.text)
    async def bug_happened(message: Message, state: FSMContext) -> None:
        await state.update_data(what_happened=beta.clip_text(message.text))
        await state.set_state(BugReport.expected)
        await message.answer("3) Что вы ожидали?")

    @router.message(BugReport.expected, F.text)
    async def bug_expected(message: Message, state: FSMContext) -> None:
        await state.update_data(what_expected=beta.clip_text(message.text))
        await state.set_state(BugReport.device)
        await message.answer("4) Устройство:", reply_markup=kb.beta_bug_device_kb())

    @router.callback_query(BugReport.device, F.data.startswith("beta:bug:device:"))
    async def bug_device(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            await callback.answer()
            return
        await state.update_data(device_class=callback.data.rsplit(":", 1)[-1])
        await state.set_state(BugReport.device_note)
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "5) Модель устройства и версия Telegram (необязательно):",
                reply_markup=kb.beta_bug_skip_kb(callback="beta:bug:skip_note"),
            )

    @router.callback_query(BugReport.device_note, F.data == "beta:bug:skip_note")
    async def bug_skip_note(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(device_note=None)
        await state.set_state(BugReport.screenshot)
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "6) Скриншот (необязательно). Пришлите фото или пропустите:",
                reply_markup=kb.beta_bug_skip_kb(callback="beta:bug:skip_photo"),
            )

    @router.message(BugReport.device_note, F.text)
    async def bug_device_note(message: Message, state: FSMContext) -> None:
        await state.update_data(
            device_note=beta.clip_text(message.text, beta.MAX_DEVICE_NOTE)
        )
        await state.set_state(BugReport.screenshot)
        await message.answer(
            "6) Скриншот (необязательно). Пришлите фото или пропустите:",
            reply_markup=kb.beta_bug_skip_kb(callback="beta:bug:skip_photo"),
        )

    @router.callback_query(BugReport.screenshot, F.data == "beta:bug:skip_photo")
    async def bug_skip_photo(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(photo_file_id=None)
        await state.set_state(BugReport.severity)
        await callback.answer()
        if callback.message:
            await callback.message.answer(
                "7) Насколько мешает?",
                reply_markup=kb.beta_bug_severity_kb(),
            )

    @router.message(BugReport.screenshot, F.photo)
    async def bug_photo(message: Message, state: FSMContext) -> None:
        file_id = message.photo[-1].file_id if message.photo else None
        await state.update_data(photo_file_id=file_id)
        await state.set_state(BugReport.severity)
        await message.answer(
            "7) Насколько мешает?",
            reply_markup=kb.beta_bug_severity_kb(),
        )

    @router.callback_query(BugReport.severity, F.data.startswith("beta:bug:sev:"))
    async def bug_severity(callback: CallbackQuery, state: FSMContext) -> None:
        user = callback.from_user
        if user is None or not callback.data:
            await callback.answer()
            return
        severity = callback.data.rsplit(":", 1)[-1]
        data = await state.get_data()
        photo_file_id = data.get("photo_file_id")
        await state.clear()
        await callback.answer()

        async with session_scope() as session:
            db_user = await repo.get_or_create_user(
                session, telegram_id=user.id, username=user.username
            )
            bug = await beta.create_bug(
                session,
                user_id=db_user.id,
                severity=severity,
                device_class=str(data.get("device_class") or "other"),
                device_note=data.get("device_note"),
                what_did=str(data.get("what_did") or ""),
                what_happened=str(data.get("what_happened") or ""),
                what_expected=str(data.get("what_expected") or ""),
            )
            user_pk = db_user.id
            if bug is None:
                if callback.message:
                    await callback.message.answer(
                        "Лимит: не больше 3 обращений в сутки. Попробуйте завтра."
                    )
                return
            ticket_id = bug.id

        if callback.message:
            await callback.message.answer(
                f"Принято. Номер обращения: <b>BUG-{ticket_id}</b>. Спасибо!",
                parse_mode="HTML",
                reply_markup=kb.main_menu(settings.telegram_webapp_url),
            )

        admin_chat = settings.admin_telegram_chat_id
        if admin_chat and settings.admin_alerts_enabled:
            report = (
                f"<b>BUG-{ticket_id}</b> · {severity}\n"
                f"device={data.get('device_class')}\n"
                f"note={beta.clip_text(str(data.get('device_note') or '—'), 80)}\n\n"
                f"<b>Делали:</b> {beta.clip_text(str(data.get('what_did') or ''), 400)}\n"
                f"<b>Произошло:</b> {beta.clip_text(str(data.get('what_happened') or ''), 400)}\n"
                f"<b>Ожидали:</b> {beta.clip_text(str(data.get('what_expected') or ''), 400)}\n"
                f"user_pk={user_pk}"
            )
            try:
                await bot.send_message(int(admin_chat), report, parse_mode="HTML")
                if photo_file_id:
                    await bot.send_photo(
                        int(admin_chat),
                        photo=photo_file_id,
                        caption=f"BUG-{ticket_id}",
                    )
            except Exception:
                logger.exception("Failed to notify admin about BUG-%s", ticket_id)

    @router.message(Command("beta_status"))
    async def cmd_beta_status(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with session_scope() as session:
            snap = await beta.beta_status_snapshot(session)
        codes = ",".join(sorted(settings.beta_invite_code_set)) or "—"
        await message.answer(
            "Beta status\n"
            f"enabled={settings.beta_enabled}\n"
            f"paused={snap['paused']}\n"
            f"codes={codes}\n"
            f"participants={snap['participants']} active={snap['active']}\n"
            f"surveys_done={snap['surveys_completed']}\n"
            f"bugs_open={snap['bugs_open']}\n"
            f"pending_jobs={snap['pending_jobs']}"
        )

    @router.message(Command("beta_feedback"))
    async def cmd_beta_feedback(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with session_scope() as session:
            rows = await beta.list_recent_feedback(session, limit=10)
        if not rows:
            await message.answer("Пока нет завершённых опросов.")
            return
        lines = [
            f"#{s.id} user={s.user_id} result={s.result} "
            f"clarity={s.clarity_score} text={beta.clip_text(s.free_text or '', 80)}"
            for s in rows
        ]
        await message.answer("\n".join(lines))

    @router.message(Command("beta_bugs"))
    async def cmd_beta_bugs(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with session_scope() as session:
            rows = await beta.list_open_bugs(session, limit=15)
        if not rows:
            await message.answer("Открытых багов нет.")
            return
        await message.answer(
            "\n".join(
                f"BUG-{b.id} {b.severity} {b.device_class} user={b.user_id}" for b in rows
            )
        )

    @router.message(Command("beta_pause"))
    async def cmd_beta_pause(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with session_scope() as session:
            await beta.set_beta_paused(session, paused=True)
        await message.answer("Beta messaging paused.")

    @router.message(Command("beta_resume"))
    async def cmd_beta_resume(message: Message) -> None:
        if not _is_admin(message, settings):
            return
        async with session_scope() as session:
            await beta.set_beta_paused(session, paused=False)
        await message.answer("Beta messaging resumed.")

    return router
