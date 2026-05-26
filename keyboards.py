# keyboards.py
import calendar
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

MONTHS_UA = ["", "Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
             "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]


# ── Головне меню ────────────────────────────────────────
def main_menu(is_owner: bool = False) -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📋 Статус"),          KeyboardButton(text="🔍 Пошук по архіву")],
        [KeyboardButton(text="🟢 Моніторинг live"), KeyboardButton(text="⏹ Стоп")],
        [KeyboardButton(text="🆘 Пошук зниклих"),   KeyboardButton(text="⚙️ Управління")],
    ]
    if is_owner:
        keyboard.append([KeyboardButton(text="➕ Додати користувача"), KeyboardButton(text="🗑 Видалити користувача")])
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ── Меню управління ─────────────────────────────────────
def management_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="📡 Канали"),           KeyboardButton(text="🔑 Ключові слова")],
        [KeyboardButton(text="📅 Період"),           KeyboardButton(text="➕ Додати канал")],
        [KeyboardButton(text="🗑 Видалити канал"),   KeyboardButton(text="➕ Додати слово")],
        [KeyboardButton(text="🗑 Видалити слово"),   KeyboardButton(text="🧠 Логіка пошуку")],
        [KeyboardButton(text="👥 Користувачі")],
        [KeyboardButton(text="◀️ Назад у меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ── Меню пошуку зниклих ────────────────────────────────
def missing_persons_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🔍 Пошук за ПІБ")],
        [KeyboardButton(text="📊 Статистика зниклих")],
        [KeyboardButton(text="ℹ️ Інформація")],
        [KeyboardButton(text="◀️ Назад у меню")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# ── Вибір каналів ───────────────────────────────────────
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


# ── Вибір ключових слів ─────────────────────────────────
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


def classifier_mode_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    labels = {
        "legacy": "Legacy",
        "shadow": "Shadow",
        "v2": "V2",
    }
    buttons = []
    for mode in ("legacy", "shadow", "v2"):
        check = "☑️" if current_mode == mode else "☐"
        buttons.append([
            InlineKeyboardButton(
                text=f"{check} {labels[mode]}",
                callback_data=f"classifier_mode:{mode}"
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Календар ────────────────────────────────────────────
def calendar_keyboard(year: int, month: int, prefix: str) -> InlineKeyboardMarkup:
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
