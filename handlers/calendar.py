# handlers/calendar.py
import logging
from datetime import datetime

from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from config import is_admin, notify_owners, load_data, save_data
from keyboards import calendar_keyboard, main_menu
from states import CalendarState

router = Router()
logger = logging.getLogger(__name__)


# ── Показати календар ───────────────────────────────────
@router.message(F.text == "📅 Період")
async def show_period(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    d         = load_data()
    date_from = d.get("date_from") or "не вказано"
    date_to   = d.get("date_to")   or "не вказано"
    now       = datetime.now()
    await state.set_state(CalendarState.picking_from)
    await msg.answer(
        f"📅 <b>Поточний період:</b> {date_from} — {date_to}\n\n"
        f"Вибери дату <b>початку</b> періоду:",
        parse_mode="HTML",
        reply_markup=calendar_keyboard(now.year, now.month, "cal_from")
    )


# ── Вибір дати початку ──────────────────────────────────
@router.callback_query(F.data.startswith("cal_from:"))
async def cal_from_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    parts  = callback.data.split(":")
    action = parts[1]
    if action in ("prev", "next"):
        year, month = int(parts[2]), int(parts[3])
        if action == "prev":
            month -= 1
            if month < 1: month = 12; year -= 1
        else:
            month += 1
            if month > 12: month = 1; year += 1
        await callback.message.edit_reply_markup(
            reply_markup=calendar_keyboard(year, month, "cal_from")
        )
        await callback.answer()
    elif action == "day":
        year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
        date_from = datetime(year, month, day)
        await state.update_data(date_from=date_from.strftime("%d.%m.%Y"))
        await state.set_state(CalendarState.picking_to)
        await callback.message.edit_text(
            f"✅ Дата початку: <b>{date_from.strftime('%d.%m.%Y')}</b>\n\n"
            f"Тепер вибери дату <b>кінця</b> періоду:",
            parse_mode="HTML",
            reply_markup=calendar_keyboard(year, month, "cal_to")
        )
        await callback.answer()


# ── Вибір дати кінця ────────────────────────────────────
@router.callback_query(F.data.startswith("cal_to:"))
async def cal_to_handler(callback: types.CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id): return
    parts  = callback.data.split(":")
    action = parts[1]
    if action in ("prev", "next"):
        year, month = int(parts[2]), int(parts[3])
        if action == "prev":
            month -= 1
            if month < 1: month = 12; year -= 1
        else:
            month += 1
            if month > 12: month = 1; year += 1
        await callback.message.edit_reply_markup(
            reply_markup=calendar_keyboard(year, month, "cal_to")
        )
        await callback.answer()
    elif action == "day":
        year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
        date_to      = datetime(year, month, day)
        data         = await state.get_data()
        date_from_dt = datetime.strptime(data["date_from"], "%d.%m.%Y")
        if date_to < date_from_dt:
            await callback.answer(
                "❌ Дата кінця не може бути раніше дати початку!", show_alert=True
            )
            return
        d = load_data()
        d["date_from"] = data["date_from"]
        d["date_to"]   = date_to.strftime("%d.%m.%Y")
        save_data(d)
        await state.clear()
        await callback.message.edit_text(
            f"✅ <b>Період встановлено:</b>\n"
            f"з <b>{d['date_from']}</b> по <b>{d['date_to']}</b>",
            parse_mode="HTML"
        )
        await notify_owners(
            callback.bot, f"📅 Період: {d['date_from']} — {d['date_to']}",
            reply_markup=main_menu(is_owner=True)
        )
        await callback.answer()


# ── Ігнор кліків на заголовки календаря ────────────────
@router.callback_query(F.data == "cal_ignore")
async def cal_ignore(callback: types.CallbackQuery):
    await callback.answer()
