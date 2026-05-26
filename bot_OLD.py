import asyncio
import os
import json
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


from telethon import TelegramClient, events
from telethon.errors import FloodWaitError

load_dotenv()
from keywords import KEYWORD_FORMS, KEYWORD_TO_SHEET, find_matching_keyword, count_keyword_occurrences
from sheets import get_spreadsheet, load_all_existing_urls, append_to_sheet, ensure_header

BOT_TOKEN      = os.getenv("BOT_TOKEN")
API_ID         = int(os.getenv("API_ID"))
API_HASH       = os.getenv("API_HASH")
ADMIN_ID       = int(os.getenv("ADMIN_CHAT_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ALERT_CHANNEL = os.getenv("ALERT_CHANNEL", None)
DATA_FILE      = "monitor_data.json"


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


MIN_HITS_OLD = 1
MIN_HITS_NEW = 1

# ── Збереження налаштувань ──────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "channels": [],
        "keywords": [],
        "live_active_channels": [],
        "live_active_keywords": [],
        "arc_active_channels": [],
        "arc_active_keywords": [],
        "date_from": None,
        "date_to": None,
        "monitoring": False
    }


def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── FSM стани ───────────────────────────────────────────
class AddChannel(StatesGroup):
    waiting = State()

class AddKeyword(StatesGroup):
    waiting = State()

class DeleteKeyword(StatesGroup):
    waiting = State()

class DeleteChannel(StatesGroup):
    waiting = State()

class CalendarState(StatesGroup):
    picking_from = State()
    picking_to   = State()


# ── Ініціалізація ───────────────────────────────────────
bot     = Bot(token=BOT_TOKEN)
dp      = Dispatcher(storage=MemoryStorage())
userbot = TelegramClient("monitor_session", API_ID, API_HASH)


# ── Меню ────────────────────────────────────────────────
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📋 Статус"),           KeyboardButton(text="🔍 Пошук по архіву")],
        [KeyboardButton(text="🟢 Моніторинг live"),  KeyboardButton(text="⏹ Стоп")],
        [KeyboardButton(text="📡 Канали"),            KeyboardButton(text="🔑 Ключові слова")],
        [KeyboardButton(text="📅 Період"),            KeyboardButton(text="➕ Додати канал")],
        [KeyboardButton(text="➕ Додати слово"),      KeyboardButton(text="🗑 Видалити канал")],
        [KeyboardButton(text="🗑 Видалити слово")],
    ], resize_keyboard=True)


# ── Inline клавіатура вибору каналів ────────────────────
def channels_selection_keyboard(channels: list, active: list, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        check = "☑️" if ch in active else "☐"
        buttons.append([InlineKeyboardButton(
            text=f"{check} @{ch}",
            callback_data=f"{prefix}_ch_toggle:{ch}"
        )])
    buttons.append([
        InlineKeyboardButton(text="✅ Вибрати всі", callback_data=f"{prefix}_ch_all"),
        InlineKeyboardButton(text="❌ Зняти всі",   callback_data=f"{prefix}_ch_none"),
    ])
    buttons.append([
        InlineKeyboardButton(text="➡️ Далі — вибір ключів", callback_data=f"{prefix}_ch_next"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Inline клавіатура вибору ключів ─────────────────────
def keywords_selection_keyboard(keywords: list, active: list, prefix: str) -> InlineKeyboardMarkup:
    buttons = []
    row = []
    for i, kw in enumerate(keywords):
        check = "☑️" if kw in active else "☐"
        row.append(InlineKeyboardButton(
            text=f"{check} {kw}",
            callback_data=f"{prefix}_kw_toggle:{kw}"
        ))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton(text="✅ Вибрати всі", callback_data=f"{prefix}_kw_all"),
        InlineKeyboardButton(text="❌ Зняти всі",   callback_data=f"{prefix}_kw_none"),
    ])
    buttons.append([
        InlineKeyboardButton(text="🚀 Запустити", callback_data=f"{prefix}_kw_start"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Календар ────────────────────────────────────────────

MONTHS_UA = ["", "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
             "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]

def calendar_keyboard(year: int, month: int, prefix: str) -> InlineKeyboardMarkup:
    import calendar
    buttons = []
    buttons.append([
        InlineKeyboardButton(text="◀️", callback_data=f"{prefix}:prev:{year}:{month}"),
        InlineKeyboardButton(text=f"{MONTHS_UA[month]} {year}", callback_data="cal_ignore"),
        InlineKeyboardButton(text="▶️", callback_data=f"{prefix}:next:{year}:{month}"),
    ])
    buttons.append([
        InlineKeyboardButton(text=d, callback_data="cal_ignore")
        for d in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
    ])
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal_ignore"))
            else:
                row.append(InlineKeyboardButton(
                    text=str(day),
                    callback_data=f"{prefix}:day:{year}:{month}:{day}"
                ))
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ── Команди ─────────────────────────────────────────────

@dp.message(Command("start"))
async def cmd_start(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    await msg.answer("👋 Привіт! Я бот-монітор Telegram каналів.", reply_markup=main_menu())


@dp.message(F.text == "📋 Статус")
async def status(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    icon      = "🟢 Активний" if d["monitoring"] else "🔴 Зупинений"
    date_from = d.get("date_from") or "не вказано"
    date_to   = d.get("date_to")   or "не вказано"
    live_ch   = d.get("live_active_channels", [])
    live_kw   = d.get("live_active_keywords", [])
    arc_ch    = d.get("arc_active_channels", [])
    arc_kw    = d.get("arc_active_keywords", [])
    await msg.answer(
        f"<b>Статус:</b> {icon}\n"
        f"<b>Всіх каналів:</b> {len(d['channels'])}\n"
        f"<b>Всіх ключів:</b> {len(d['keywords'])}\n\n"
        f"🟢 <b>Live:</b> каналів {len(live_ch)}, ключів {len(live_kw)}\n"
        f"🔍 <b>Архів:</b> каналів {len(arc_ch)}, ключів {len(arc_kw)}\n"
        f"📅 <b>Період архіву:</b> {date_from} — {date_to}",
        parse_mode="HTML"
    )


@dp.message(F.text == "📡 Канали")
async def show_channels(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["channels"]:
        await msg.answer("Канали не додані. Натисни ➕ Додати канал")
        return
    text = "📡 <b>Канали:</b>\n" + "\n".join(f"• @{c}" for c in d["channels"])
    await msg.answer(text, parse_mode="HTML")


@dp.message(F.text == "🔑 Ключові слова")
async def show_keywords(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["keywords"]:
        await msg.answer("Слова не додані. Натисни ➕ Додати слово")
        return
    text = "🔑 <b>Всі ключові слова:</b>\n" + "\n".join(f"• {k}" for k in d["keywords"])
    await msg.answer(text, parse_mode="HTML")


# ── Період — календар ────────────────────────────────────
@dp.message(F.text == "📅 Період")
async def show_period(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    date_from = d.get("date_from") or "не вказано"
    date_to   = d.get("date_to")   or "не вказано"
    now = datetime.now()
    await state.set_state(CalendarState.picking_from)
    await msg.answer(
        f"📅 <b>Поточний період:</b> {date_from} — {date_to}\n\n"
        f"Вибери дату <b>початку</b> періоду:",
        parse_mode="HTML",
        reply_markup=calendar_keyboard(now.year, now.month, "cal_from")
    )


@dp.callback_query(F.data.startswith("cal_from:"))
async def cal_from_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
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
        await callback.message.edit_reply_markup(reply_markup=calendar_keyboard(year, month, "cal_from"))
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


@dp.callback_query(F.data.startswith("cal_to:"))
async def cal_to_handler(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
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
        await callback.message.edit_reply_markup(reply_markup=calendar_keyboard(year, month, "cal_to"))
        await callback.answer()
    elif action == "day":
        year, month, day = int(parts[2]), int(parts[3]), int(parts[4])
        date_to      = datetime(year, month, day)
        data         = await state.get_data()
        date_from_dt = datetime.strptime(data["date_from"], "%d.%m.%Y")
        if date_to < date_from_dt:
            await callback.answer("❌ Дата кінця не може бути раніше дати початку!", show_alert=True)
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
        await bot.send_message(ADMIN_ID, f"📅 Період: {d['date_from']} — {d['date_to']}", reply_markup=main_menu())
        await callback.answer()


@dp.callback_query(F.data == "cal_ignore")
async def cal_ignore(callback: types.CallbackQuery):
    await callback.answer()


# ── Додати канал ────────────────────────────────────────
@dp.message(F.text == "➕ Додати канал")
async def ask_channel(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(AddChannel.waiting)
    await msg.answer(
        "Введи username каналу без @\nМожна кілька через кому: ternopil_tviy, huyovyi_ternopil",
        reply_markup=ReplyKeyboardRemove()
    )


@dp.message(AddChannel.waiting)
async def add_channel(msg: types.Message, state: FSMContext):
    d = load_data()
    channels = [c.strip().lstrip("@") for c in msg.text.split(",") if c.strip()]
    added = []
    for ch in channels:
        if ch not in d["channels"]:
            d["channels"].append(ch)
            added.append(ch)
    save_data(d)
    if added:
        await msg.answer(f"✅ Додано: {', '.join('@'+c for c in added)}", reply_markup=main_menu())
    else:
        await msg.answer("Всі ці канали вже є у списку.", reply_markup=main_menu())
    await state.clear()


# ── Додати слово ────────────────────────────────────────
@dp.message(F.text == "➕ Додати слово")
async def ask_keyword(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    await state.set_state(AddKeyword.waiting)
    await msg.answer("Введи ключові слова через кому:", reply_markup=ReplyKeyboardRemove())


@dp.message(AddKeyword.waiting)
async def add_keyword(msg: types.Message, state: FSMContext):
    d = load_data()
    words = [w.strip().lower() for w in msg.text.split(",") if w.strip()]
    added = []
    for kw in words:
        if kw not in d["keywords"]:
            d["keywords"].append(kw)
            added.append(kw)
    save_data(d)
    if added:
        await msg.answer(f"✅ Додано слова: {', '.join(added)}", reply_markup=main_menu())
    else:
        await msg.answer("Всі ці слова вже є у списку.", reply_markup=main_menu())
    await state.clear()


# ── Видалити канал ──────────────────────────────────────
@dp.message(F.text == "🗑 Видалити канал")
async def ask_delete_channel(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["channels"]:
        await msg.answer("Список каналів порожній.")
        return
    text = "Введи username каналу для видалення:\n\n" + "\n".join(f"• @{c}" for c in d["channels"])
    await state.set_state(DeleteChannel.waiting)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())


@dp.message(DeleteChannel.waiting)
async def confirm_delete_channel(msg: types.Message, state: FSMContext):
    d = load_data()
    ch = msg.text.strip().lstrip("@")
    if ch in d["channels"]:
        d["channels"].remove(ch)
        d["live_active_channels"] = [c for c in d.get("live_active_channels", []) if c != ch]
        d["arc_active_channels"]  = [c for c in d.get("arc_active_channels",  []) if c != ch]
        save_data(d)
        await msg.answer(f"✅ Канал @{ch} видалено!", reply_markup=main_menu())
    else:
        await msg.answer(f"Канал @{ch} не знайдено.", reply_markup=main_menu())
    await state.clear()


# ── Видалити слово ──────────────────────────────────────
@dp.message(F.text == "🗑 Видалити слово")
async def ask_delete_keyword(msg: types.Message, state: FSMContext):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["keywords"]:
        await msg.answer("Список слів порожній.")
        return
    text = "Введи слово для видалення:\n\n" + "\n".join(f"• {k}" for k in d["keywords"])
    await state.set_state(DeleteKeyword.waiting)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())


@dp.message(DeleteKeyword.waiting)
async def confirm_delete_keyword(msg: types.Message, state: FSMContext):
    d = load_data()
    kw = msg.text.strip().lower()
    if kw in d["keywords"]:
        d["keywords"].remove(kw)
        d["live_active_keywords"] = [k for k in d.get("live_active_keywords", []) if k != kw]
        d["arc_active_keywords"]  = [k for k in d.get("arc_active_keywords",  []) if k != kw]
        save_data(d)
        await msg.answer(f"✅ Слово «{kw}» видалено!", reply_markup=main_menu())
    else:
        await msg.answer(f"Слово «{kw}» не знайдено.", reply_markup=main_menu())
    await state.clear()


# ════════════════════════════════════════════════════════
# ── ПОШУК ПО АРХІВУ ─────────────────────────────────────
# ════════════════════════════════════════════════════════

@dp.message(F.text == "🔍 Пошук по архіву")
async def archive_search_start(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["channels"]:
        await msg.answer("⚠️ Спочатку додай канали!")
        return
    if not d["keywords"]:
        await msg.answer("⚠️ Спочатку додай ключові слова!")
        return
    if not d.get("date_from") or not d.get("date_to"):
        await msg.answer("⚠️ Спочатку встанови період через кнопку 📅 Період!")
        return
    if not d.get("arc_active_channels"):
        d["arc_active_channels"] = d["channels"].copy()
        save_data(d)
    await msg.answer(
        f"📡 <b>Крок 1/2 — Вибери канали для пошуку:</b>",
        parse_mode="HTML",
        reply_markup=channels_selection_keyboard(d["channels"], d["arc_active_channels"], "arc")
    )


@dp.callback_query(F.data.startswith("arc_ch_toggle:"))
async def arc_ch_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    ch = callback.data.split("arc_ch_toggle:")[1]
    d  = load_data()
    active = d.get("arc_active_channels", [])
    if ch in active: active.remove(ch)
    else: active.append(ch)
    d["arc_active_channels"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], active, "arc")
    )
    await callback.answer()

@dp.callback_query(F.data == "arc_ch_all")
async def arc_ch_all(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["arc_active_channels"] = d["channels"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], d["arc_active_channels"], "arc")
    )
    await callback.answer("✅ Всі вибрані")

@dp.callback_query(F.data == "arc_ch_none")
async def arc_ch_none(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["arc_active_channels"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], [], "arc")
    )
    await callback.answer("❌ Всі зняті")

@dp.callback_query(F.data == "arc_ch_next")
async def arc_ch_next(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d.get("arc_active_channels"):
        await callback.answer("⚠️ Вибери хоча б один канал!", show_alert=True)
        return
    if not d.get("arc_active_keywords"):
        d["arc_active_keywords"] = d["keywords"].copy()
        save_data(d)
    await callback.message.edit_text(
        f"🔑 <b>Крок 2/2 — Вибери ключові слова:</b>",
        parse_mode="HTML",
        reply_markup=keywords_selection_keyboard(d["keywords"], d["arc_active_keywords"], "arc")
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("arc_kw_toggle:"))
async def arc_kw_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    kw = callback.data.split("arc_kw_toggle:")[1]
    d  = load_data()
    active = d.get("arc_active_keywords", [])
    if kw in active: active.remove(kw)
    else: active.append(kw)
    d["arc_active_keywords"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], active, "arc")
    )
    await callback.answer()

@dp.callback_query(F.data == "arc_kw_all")
async def arc_kw_all(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["arc_active_keywords"] = d["keywords"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], d["arc_active_keywords"], "arc")
    )
    await callback.answer("✅ Всі вибрані")

@dp.callback_query(F.data == "arc_kw_none")
async def arc_kw_none(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["arc_active_keywords"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], [], "arc")
    )
    await callback.answer("❌ Всі зняті")

@dp.callback_query(F.data == "arc_kw_start")
async def arc_kw_start(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d.get("arc_active_keywords"):
        await callback.answer("⚠️ Вибери хоча б одне слово!", show_alert=True)
        return
    date_from_str = d.get("date_from")
    date_to_str   = d.get("date_to")
    if not date_from_str or not date_to_str:
        await callback.answer("⚠️ Спочатку встанови період!", show_alert=True)
        return
    since = datetime.strptime(date_from_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    until = datetime.strptime(date_to_str,   "%d.%m.%Y").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await bot.send_message(ADMIN_ID,
        f"⏳ Запускаю пошук по архіву...\n"
        f"📅 Період: <b>{date_from_str}</b> — <b>{date_to_str}</b>\n"
        f"📡 Каналів: {len(d['arc_active_channels'])}\n"
        f"🔑 Слова: {', '.join(d['arc_active_keywords'])}",
        parse_mode="HTML"
    )
    await scan_old_posts(since, until, d)


# ════════════════════════════════════════════════════════
# ── МОНІТОРИНГ LIVE ──────────────────────────────────────
# ════════════════════════════════════════════════════════

@dp.message(F.text == "🟢 Моніторинг live")
async def live_monitoring_start(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d["channels"]:
        await msg.answer("⚠️ Спочатку додай канали!")
        return
    if not d["keywords"]:
        await msg.answer("⚠️ Спочатку додай ключові слова!")
        return
    if not d.get("live_active_channels"):
        d["live_active_channels"] = d["channels"].copy()
        save_data(d)
    await msg.answer(
        f"📡 <b>Крок 1/2 — Вибери канали для моніторингу:</b>",
        parse_mode="HTML",
        reply_markup=channels_selection_keyboard(d["channels"], d["live_active_channels"], "live")
    )


@dp.callback_query(F.data.startswith("live_ch_toggle:"))
async def live_ch_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    ch = callback.data.split("live_ch_toggle:")[1]
    d  = load_data()
    active = d.get("live_active_channels", [])
    if ch in active: active.remove(ch)
    else: active.append(ch)
    d["live_active_channels"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], active, "live")
    )
    await callback.answer()

@dp.callback_query(F.data == "live_ch_all")
async def live_ch_all(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["live_active_channels"] = d["channels"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], d["live_active_channels"], "live")
    )
    await callback.answer("✅ Всі вибрані")

@dp.callback_query(F.data == "live_ch_none")
async def live_ch_none(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["live_active_channels"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], [], "live")
    )
    await callback.answer("❌ Всі зняті")

@dp.callback_query(F.data == "live_ch_next")
async def live_ch_next(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d.get("live_active_channels"):
        await callback.answer("⚠️ Вибери хоча б один канал!", show_alert=True)
        return
    if not d.get("live_active_keywords"):
        d["live_active_keywords"] = d["keywords"].copy()
        save_data(d)
    await callback.message.edit_text(
        f"🔑 <b>Крок 2/2 — Вибери ключові слова:</b>",
        parse_mode="HTML",
        reply_markup=keywords_selection_keyboard(d["keywords"], d["live_active_keywords"], "live")
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("live_kw_toggle:"))
async def live_kw_toggle(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    kw = callback.data.split("live_kw_toggle:")[1]
    d  = load_data()
    active = d.get("live_active_keywords", [])
    if kw in active: active.remove(kw)
    else: active.append(kw)
    d["live_active_keywords"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], active, "live")
    )
    await callback.answer()

@dp.callback_query(F.data == "live_kw_all")
async def live_kw_all(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["live_active_keywords"] = d["keywords"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], d["live_active_keywords"], "live")
    )
    await callback.answer("✅ Всі вибрані")

@dp.callback_query(F.data == "live_kw_none")
async def live_kw_none(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    d["live_active_keywords"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], [], "live")
    )
    await callback.answer("❌ Всі зняті")

@dp.callback_query(F.data == "live_kw_start")
async def live_kw_start(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    d = load_data()
    if not d.get("live_active_keywords"):
        await callback.answer("⚠️ Вибери хоча б одне слово!", show_alert=True)
        return
    d["monitoring"] = True
    save_data(d)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await bot.send_message(ADMIN_ID,
        f"🟢 Запускаю моніторинг live...\n"
        f"📡 Каналів: {len(d['live_active_channels'])}\n"
        f"🔑 Слова: {', '.join(d['live_active_keywords'])}",
        parse_mode="HTML"
    )
    await start_monitoring(d)


# ── Пошук старих постів ─────────────────────────────────
async def scan_old_posts(since, until, d):
    total   = 0
    skipped = 0
    try:
        spreadsheet   = get_spreadsheet()
        existing_urls = load_all_existing_urls(spreadsheet)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        await bot.send_message(ADMIN_ID, f"⚠️ Google Sheets помилка:\n<code>{str(e)}</code>", parse_mode="HTML")
        logger.error(f"Google Sheets повна помилка:\n{err}")
        spreadsheet   = None
        existing_urls = {}

    await bot.send_message(ADMIN_ID,
        f"🔍 Сканую пости з <b>{since.strftime('%d.%m.%Y')}</b> по <b>{until.strftime('%d.%m.%Y')}</b>...",
        parse_mode="HTML"
    )

    for channel in d["arc_active_channels"]:
        try:
            entity = await userbot.get_entity(channel)
            await bot.send_message(ADMIN_ID, f"📡 Сканую @{channel}...")
            async for message in userbot.iter_messages(entity, limit=500):
                msg_date = message.date.replace(tzinfo=timezone.utc)
                if msg_date < since:
                    break
                if msg_date > until:
                    continue
                text    = message.text or ""
                matched = find_matching_keyword(text, d["arc_active_keywords"], min_hits=MIN_HITS_OLD)
                if not matched:
                    continue

                username    = getattr(entity, "username", None)
                title       = escape_html(getattr(entity, "title", "Невідомо"))
                subscribers = getattr(entity, "participants_count", "—")
                description = escape_html(getattr(entity, "about", "—") or "—")
                verified    = "✅ Так" if getattr(entity, "verified", False) else "Ні"
                restricted  = "⚠️ Так" if getattr(entity, "restricted", False) else "Ні"
                scam        = "🚨 Так" if getattr(entity, "scam", False) else "Ні"
                url         = f"https://t.me/{username}/{message.id}" if username else "—"
                date_str    = message.date.strftime("%d.%m.%Y")
                time_str    = message.date.strftime("%H:%M")
                safe_text   = escape_html(text[:600])
                views       = getattr(message, "views", "—") or "—"
                forwards    = getattr(message, "forwards", "—") or "—"
                post_author = escape_html(getattr(message, "post_author", None) or "—")
                has_media   = "📎 Так" if message.media else "Ні"
                replies     = "—"
                if hasattr(message, "replies") and message.replies:
                    replies = str(message.replies.replies)

                if spreadsheet:
                    added = append_to_sheet(
                        spreadsheet, existing_urls, matched,
                        f"@{username or channel}", date_str, time_str, url, text
                    )
                    if not added:
                        skipped += 1

                alert = (
                    f"📌 <b>Старий пост знайдено!</b>\n\n"
                    f"🔑 <b>Ключове слово:</b> <code>{matched}</code>\n"
                    f"📂 <b>Вкладка:</b> <code>{KEYWORD_TO_SHEET.get(matched, '—')}</code>\n\n"
                    f"━━━ 📡 КАНАЛ ━━━\n"
                    f"📛 <b>Назва:</b> {title}\n"
                    f"🔗 <b>Username:</b> @{username or '—'}\n"
                    f"👥 <b>Підписники:</b> {subscribers}\n"
                    f"📝 <b>Опис:</b> {description[:150]}\n"
                    f"✅ <b>Верифікований:</b> {verified}\n"
                    f"🚫 <b>Обмежений:</b> {restricted}\n"
                    f"☠️ <b>Скам:</b> {scam}\n\n"
                    f"━━━ 📰 ПУБЛІКАЦІЯ ━━━\n"
                    f"📅 <b>Дата:</b> {date_str} {time_str}\n"
                    f"👁 <b>Перегляди:</b> {views}\n"
                    f"🔄 <b>Репости:</b> {forwards}\n"
                    f"💬 <b>Коментарі:</b> {replies}\n"
                    f"🖼 <b>Медіа:</b> {has_media}\n"
                    f"✍️ <b>Автор підпису:</b> {post_author}\n\n"
                    f"━━━ 💬 ТЕКСТ ━━━\n"
                    f"{safe_text}\n\n"
                    f"🔗 {url}"
                )
                await bot.send_message(ADMIN_ID, alert, parse_mode="HTML")
                total += 1
                await asyncio.sleep(0.5)

        except FloodWaitError as e:
            await bot.send_message(ADMIN_ID, f"⏳ Telegram просить зачекати {e.seconds} сек...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            await bot.send_message(ADMIN_ID, f"⚠️ Помилка з каналом @{channel}: {e}")

    summary = f"✅ Сканування завершено! Знайдено постів: {total}"
    if skipped:
        summary += f"\n♻️ Пропущено дублів: {skipped}"
    await bot.send_message(ADMIN_ID, summary)

# ── Моніторинг нових постів ─────────────────────────────
async def start_monitoring(d: dict):
    try:
        spreadsheet   = get_spreadsheet()
        existing_urls = load_all_existing_urls(spreadsheet)
    except Exception as e:
        import traceback
        err = traceback.format_exc()
        await bot.send_message(ADMIN_ID, f"⚠️ Google Sheets помилка:\n<code>{str(e)}</code>", parse_mode="HTML")
        logger.error(f"Google Sheets повна помилка:\n{err}")
        spreadsheet   = None
        existing_urls = {}

    @userbot.on(events.NewMessage(chats=d["live_active_channels"]))
    async def handler(event):
        d_cur = load_data()
        if not d_cur.get("monitoring"):
            return
        text    = event.message.text or ""
        matched = find_matching_keyword(text, d_cur["live_active_keywords"], min_hits=MIN_HITS_NEW)
        if not matched:
            return
        try:
            chat        = await event.get_chat()
            title       = escape_html(getattr(chat, "title", "Невідомо"))
            username    = getattr(chat, "username", None)
            subscribers = getattr(chat, "participants_count", "—")
            description = escape_html(getattr(chat, "about", "—") or "—")
            verified    = "✅ Так" if getattr(chat, "verified", False) else "Ні"
            restricted  = "⚠️ Так" if getattr(chat, "restricted", False) else "Ні"
            scam        = "🚨 Так" if getattr(chat, "scam", False) else "Ні"
            url         = f"https://t.me/{username}/{event.message.id}" if username else "—"
            date_str    = event.message.date.strftime("%d.%m.%Y")
            time_str    = event.message.date.strftime("%H:%M")
            safe_text   = escape_html(text[:600])
            views       = getattr(event.message, "views", "—") or "—"
            forwards    = getattr(event.message, "forwards", "—") or "—"
            post_author = escape_html(getattr(event.message, "post_author", None) or "—")
            has_media   = "📎 Так" if event.message.media else "Ні"
            replies     = "—"
            if hasattr(event.message, "replies") and event.message.replies:
                replies = str(event.message.replies.replies)

            if spreadsheet:
                append_to_sheet(
                    spreadsheet, existing_urls, matched,
                    f"@{username or 'unknown'}", date_str, time_str, url, text
                )

            alert = (
                f"🔔 <b>Новий пост знайдено!</b>\n\n"
                f"🔑 <b>Ключове слово:</b> <code>{matched}</code>\n"
                f"📂 <b>Вкладка:</b> <code>{KEYWORD_TO_SHEET.get(matched, '—')}</code>\n\n"
                f"━━━ 📡 КАНАЛ ━━━\n"
                f"📛 <b>Назва:</b> {title}\n"
                f"🔗 <b>Username:</b> @{username or '—'}\n"
                f"👥 <b>Підписники:</b> {subscribers}\n"
                f"📝 <b>Опис:</b> {description[:150]}\n"
                f"✅ <b>Верифікований:</b> {verified}\n"
                f"🚫 <b>Обмежений:</b> {restricted}\n"
                f"☠️ <b>Скам:</b> {scam}\n\n"
                f"━━━ 📰 ПУБЛІКАЦІЯ ━━━\n"
                f"📅 <b>Дата:</b> {date_str} {time_str}\n"
                f"👁 <b>Перегляди:</b> {views}\n"
                f"🔄 <b>Репости:</b> {forwards}\n"
                f"💬 <b>Коментарі:</b> {replies}\n"
                f"🖼 <b>Медіа:</b> {has_media}\n"
                f"✍️ <b>Автор підпису:</b> {post_author}\n\n"
                f"━━━ 💬 ТЕКСТ ━━━\n"
                f"{safe_text}\n\n"
                f"🔗 {url}"
            )
            target = int(ALERT_CHANNEL) if ALERT_CHANNEL else ADMIN_ID
            await bot.send_message(target, alert, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Помилка: {e}")

    await bot.send_message(ADMIN_ID, "🟢 Слухаю нові пости в реальному часі...")

# ── Стоп ────────────────────────────────────────────────
@dp.message(F.text == "⏹ Стоп")
async def stop_cmd(msg: types.Message):
    if msg.from_user.id != ADMIN_ID: return
    d = load_data()
    d["monitoring"] = False
    save_data(d)
    userbot.remove_event_handler(None)
    await msg.answer("🔴 Моніторинг зупинено.", reply_markup=main_menu())


# ── Запуск ───────────────────────────────────────────────
async def main():
    await userbot.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())