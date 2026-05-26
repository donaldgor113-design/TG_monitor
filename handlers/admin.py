# handlers/admin.py
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config import get_admin_ids, get_owner_ids, is_admin, is_owner, load_data, save_data
from keyboards import main_menu, classifier_mode_keyboard
from keywords import get_classifier_mode_label
from states import AddAdminUser, AddChannel, AddKeyword, DeleteAdminUser, DeleteChannel, DeleteKeyword

router = Router()
logger = logging.getLogger(__name__)


def _menu_for(user_id: int, data: dict | None = None):
    return main_menu(is_owner=is_owner(user_id, data))


# ── /start ──────────────────────────────────────────────
@router.message(Command("start"))
async def cmd_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔ У тебе немає доступу до цього бота.")
        return
    await msg.answer("👋 Привіт! Я бот-монітор Telegram каналів.", reply_markup=_menu_for(msg.from_user.id))


# ── Статус ──────────────────────────────────────────────
@router.message(F.text == "📋 Статус")
async def status(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d         = load_data()
    icon      = "🟢 Активний" if d["monitoring"] else "🔴 Зупинений"
    date_from = d.get("date_from") or "не вказано"
    date_to   = d.get("date_to")   or "не вказано"
    live_ch   = d.get("live_active_channels", [])
    live_kw   = d.get("live_active_keywords", [])
    arc_ch    = d.get("arc_active_channels", [])
    arc_kw    = d.get("arc_active_keywords", [])
    admins    = get_admin_ids(d)
    owners    = get_owner_ids(d)
    await msg.answer(
        f"<b>Статус:</b> {icon}\n"
        f"<b>Всіх каналів:</b> {len(d['channels'])}\n"
        f"<b>Всіх ключів:</b> {len(d['keywords'])}\n\n"
        f"👥 <b>Адмінів:</b> {len(admins)}\n"
        f"🛡 <b>Власників:</b> {len(owners)}\n"
        f"🧠 <b>Логіка пошуку:</b> {get_classifier_mode_label(d.get('classifier_mode', 'legacy'))}\n"
        f"🟢 <b>Live:</b> каналів {len(live_ch)}, ключів {len(live_kw)}\n"
        f"🔍 <b>Архів:</b> каналів {len(arc_ch)}, ключів {len(arc_kw)}\n"
        f"📅 <b>Період архіву:</b> {date_from} — {date_to}",
        parse_mode="HTML"
    )


@router.message(F.text == "🧠 Логіка пошуку")
async def classifier_mode_menu(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    mode = d.get("classifier_mode", "legacy")
    await msg.answer(
        "🧠 <b>Режим класифікації постів</b>\n\n"
        "Legacy: поточна бойова логіка.\n"
        "Shadow: алерти йдуть по Legacy, а V2 паралельно порівнюється.\n"
        "V2: нова логіка з балами та пріоритетами.\n\n"
        f"Поточний режим: <b>{get_classifier_mode_label(mode)}</b>",
        parse_mode="HTML",
        reply_markup=classifier_mode_keyboard(mode)
    )


@router.callback_query(F.data.startswith("classifier_mode:"))
async def classifier_mode_set(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    mode = callback.data.split("classifier_mode:", 1)[1]
    if mode not in {"legacy", "shadow", "v2"}:
        await callback.answer("Невідомий режим", show_alert=True)
        return
    d = load_data()
    d["classifier_mode"] = mode
    save_data(d)
    await callback.message.edit_text(
        "🧠 <b>Режим класифікації постів</b>\n\n"
        "Legacy: поточна бойова логіка.\n"
        "Shadow: алерти йдуть по Legacy, а V2 паралельно порівнюється.\n"
        "V2: нова логіка з балами та пріоритетами.\n\n"
        f"Поточний режим: <b>{get_classifier_mode_label(mode)}</b>",
        parse_mode="HTML",
        reply_markup=classifier_mode_keyboard(mode)
    )
    await callback.answer(f"Увімкнено {get_classifier_mode_label(mode)}")


@router.message(F.text == "👥 Користувачі")
async def show_users(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    admins = get_admin_ids(d)
    owners = set(get_owner_ids(d))
    lines = []
    for user_id in admins:
        role = "owner" if user_id in owners else "admin"
        lines.append(f"• <code>{user_id}</code> — {role}")
    await msg.answer(
        "👥 <b>Користувачі з доступом</b>\n\n" + ("\n".join(lines) if lines else "Список порожній."),
        parse_mode="HTML"
    )


@router.message(F.text == "➕ Додати користувача")
async def ask_add_user(msg: types.Message, state: FSMContext):
    if not is_owner(msg.from_user.id):
        await msg.answer("⛔ Додавати користувачів можуть тільки власники.")
        return
    await state.set_state(AddAdminUser.waiting)
    await msg.answer(
        "Введи Telegram ID користувача, якому треба дати доступ:",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(AddAdminUser.waiting)
async def add_user(msg: types.Message, state: FSMContext):
    d = load_data()
    if not is_owner(msg.from_user.id, d):
        await msg.answer("⛔ Додавати користувачів можуть тільки власники.", reply_markup=_menu_for(msg.from_user.id, d))
        await state.clear()
        return
    try:
        user_id = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Потрібно ввести числовий Telegram ID.", reply_markup=_menu_for(msg.from_user.id, d))
        await state.clear()
        return
    admins = get_admin_ids(d)
    if user_id not in admins:
        admins.append(user_id)
        d["admin_ids"] = admins
        save_data(d)
        await msg.answer(f"✅ Користувача <code>{user_id}</code> додано.", parse_mode="HTML", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer(f"Користувач <code>{user_id}</code> уже має доступ.", parse_mode="HTML", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()


@router.message(F.text == "🗑 Видалити користувача")
async def ask_delete_user(msg: types.Message, state: FSMContext):
    d = load_data()
    if not is_owner(msg.from_user.id, d):
        await msg.answer("⛔ Видаляти користувачів можуть тільки власники.")
        return
    admins = get_admin_ids(d)
    text = "Введи Telegram ID користувача для видалення:\n\n" + "\n".join(f"• {uid}" for uid in admins)
    await state.set_state(DeleteAdminUser.waiting)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())


@router.message(DeleteAdminUser.waiting)
async def delete_user(msg: types.Message, state: FSMContext):
    d = load_data()
    if not is_owner(msg.from_user.id, d):
        await msg.answer("⛔ Видаляти користувачів можуть тільки власники.", reply_markup=_menu_for(msg.from_user.id, d))
        await state.clear()
        return
    try:
        user_id = int(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Потрібно ввести числовий Telegram ID.", reply_markup=_menu_for(msg.from_user.id, d))
        await state.clear()
        return
    owners = get_owner_ids(d)
    admins = get_admin_ids(d)
    if user_id in owners:
        await msg.answer("⛔ Не можна видалити власника зі списку доступу.", reply_markup=_menu_for(msg.from_user.id, d))
        await state.clear()
        return
    if user_id in admins:
        d["admin_ids"] = [uid for uid in admins if uid != user_id]
        save_data(d)
        await msg.answer(f"✅ Користувача <code>{user_id}</code> видалено.", parse_mode="HTML", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer(f"Користувача <code>{user_id}</code> не знайдено.", parse_mode="HTML", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()


# ── Канали ──────────────────────────────────────────────
@router.message(F.text == "📡 Канали")
async def show_channels(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    if not d["channels"]:
        await msg.answer("Канали не додані. Натисни ➕ Додати канал")
        return
    text = "📡 <b>Канали:</b>\n" + "\n".join(f"• @{c}" for c in d["channels"])
    await msg.answer(text, parse_mode="HTML")


# ── Ключові слова ───────────────────────────────────────
@router.message(F.text == "🔑 Ключові слова")
async def show_keywords(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    if not d["keywords"]:
        await msg.answer("Слова не додані. Натисни ➕ Додати слово")
        return
    text = "🔑 <b>Всі ключові слова:</b>\n" + "\n".join(f"• {k}" for k in d["keywords"])
    await msg.answer(text, parse_mode="HTML")


# ── Додати канал ────────────────────────────────────────
@router.message(F.text == "➕ Додати канал")
async def ask_channel(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.set_state(AddChannel.waiting)
    await msg.answer(
        "Введи username каналу без @\nМожна кілька через кому: ternopil_tviy, huyovyi_ternopil",
        reply_markup=ReplyKeyboardRemove()
    )

@router.message(AddChannel.waiting)
async def add_channel(msg: types.Message, state: FSMContext):
    d        = load_data()
    channels = [c.strip().lstrip("@").lower() for c in msg.text.split(",") if c.strip()]
    added    = []
    for ch in channels:
        if ch not in d["channels"]:
            d["channels"].append(ch)
            added.append(ch)
    save_data(d)
    if added:
        await msg.answer(f"✅ Додано: {', '.join('@'+c for c in added)}", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer("Всі ці канали вже є у списку.", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()


# ── Додати слово ────────────────────────────────────────
@router.message(F.text == "➕ Додати слово")
async def ask_keyword(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.set_state(AddKeyword.waiting)
    await msg.answer("Введи ключові слова через кому:", reply_markup=ReplyKeyboardRemove())

@router.message(AddKeyword.waiting)
async def add_keyword(msg: types.Message, state: FSMContext):
    d     = load_data()
    words = [w.strip().lower() for w in msg.text.split(",") if w.strip()]
    added = []
    for kw in words:
        if kw not in d["keywords"]:
            d["keywords"].append(kw)
            added.append(kw)
    save_data(d)
    if added:
        await msg.answer(f"✅ Додано слова: {', '.join(added)}", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer("Всі ці слова вже є у списку.", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()


# ── Видалити канал ──────────────────────────────────────
@router.message(F.text == "🗑 Видалити канал")
async def ask_delete_channel(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    if not d["channels"]:
        await msg.answer("Список каналів порожній.")
        return
    text = "Введи username каналу для видалення:\n\n" + "\n".join(f"• @{c}" for c in d["channels"])
    await state.set_state(DeleteChannel.waiting)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())

@router.message(DeleteChannel.waiting)
async def confirm_delete_channel(msg: types.Message, state: FSMContext):
    d  = load_data()
    ch = msg.text.strip().lstrip("@").lower()
    if ch in d["channels"]:
        d["channels"].remove(ch)
        d["live_active_channels"] = [c for c in d.get("live_active_channels", []) if c != ch]
        d["arc_active_channels"]  = [c for c in d.get("arc_active_channels",  []) if c != ch]
        save_data(d)
        await msg.answer(f"✅ Канал @{ch} видалено!", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer(f"Канал @{ch} не знайдено.", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()


# ── Видалити слово ──────────────────────────────────────
@router.message(F.text == "🗑 Видалити слово")
async def ask_delete_keyword(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    if not d["keywords"]:
        await msg.answer("Список слів порожній.")
        return
    text = "Введи слово для видалення:\n\n" + "\n".join(f"• {k}" for k in d["keywords"])
    await state.set_state(DeleteKeyword.waiting)
    await msg.answer(text, reply_markup=ReplyKeyboardRemove())

@router.message(DeleteKeyword.waiting)
async def confirm_delete_keyword(msg: types.Message, state: FSMContext):
    d  = load_data()
    kw = msg.text.strip().lower()
    if kw in d["keywords"]:
        d["keywords"].remove(kw)
        d["live_active_keywords"] = [k for k in d.get("live_active_keywords", []) if k != kw]
        d["arc_active_keywords"]  = [k for k in d.get("arc_active_keywords",  []) if k != kw]
        save_data(d)
        await msg.answer(f"✅ Слово «{kw}» видалено!", reply_markup=_menu_for(msg.from_user.id, d))
    else:
        await msg.answer(f"Слово «{kw}» не знайдено.", reply_markup=_menu_for(msg.from_user.id, d))
    await state.clear()
