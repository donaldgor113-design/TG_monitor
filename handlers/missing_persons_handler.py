"""
Обробники для пошуку зниклих осіб.
"""

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import notify_admins
from keyboards import missing_persons_menu

router = Router()


class MissingPersonsStates(StatesGroup):
    """FSM стани для пошуку зниклих."""
    waiting_for_pib = State()


@router.message(F.text == "🆘 Пошук зниклих")
async def missing_persons_menu_handler(message: Message):
    """Показати меню пошуку зниклих."""
    await message.answer(
        "🆘 <b>Пошук зниклих людей</b>\n\n"
        "Тут ти можеш шукати інформацію про зниклих осіб у спеціалізованих каналах.",
        parse_mode="HTML",
        reply_markup=missing_persons_menu()
    )


@router.message(F.text == "🔍 Пошук за ПІБ")
async def search_by_pib_handler(message: Message, state: FSMContext):
    """Запросити ПІБ для пошуку."""
    await message.answer(
        "🔍 <b>Пошук за ПІБ</b>\n\n"
        "Введіть прізвище та ім'я (приклад: <code>Петренко Петро</code>):",
        parse_mode="HTML"
    )
    await state.set_state(MissingPersonsStates.waiting_for_pib)


@router.message(MissingPersonsStates.waiting_for_pib)
async def process_pib_search(message: Message, state: FSMContext):
    """Обробити пошук за введеним ПІБ."""
    pib = message.text.strip()

    if not pib or len(pib) < 3:
        await message.answer("❌ ПІБ занадто коротко. Введіть прізвище та ім'я.")
        return

    await message.answer(
        f"🔍 Шукаю <code>{pib}</code> по каналах...\n"
        f"⏳ Це може зайняти 2-5 хвилин. Чекай...",
        parse_mode="HTML"
    )

    # TODO: Це буде реалізовано коли будуть готові залежності (gspread, telethon)
    # Тут буде:
    # 1. Завантажити список каналів з Google Sheets
    # 2. Шукати по каналах за ПІБ (з queue-based підходом)
    # 3. Записати результати в Sheets
    # 4. Надіслати адміну алерт

    await message.answer(
        "⚠️ <b>Функція в розробці</b>\n\n"
        "Пошук буде готовий коли буде інтегрована Google Sheets API.",
        parse_mode="HTML"
    )

    await state.clear()


@router.message(F.text == "📊 Статистика зниклих")
async def missing_stats_handler(message: Message):
    """Показати статистику по зниклих."""
    await message.answer(
        "📊 <b>Статистика</b>\n\n"
        "⚠️ Функція в розробці",
        parse_mode="HTML"
    )


@router.message(F.text == "ℹ️ Інформація")
async def missing_info_handler(message: Message):
    """Показати інформацію про функцію."""
    await message.answer(
        "ℹ️ <b>Інформація про пошук зниклих</b>\n\n"
        "<b>Що робить</b>\n"
        "Шукає інформацію про зниклих людей у спеціалізованих Telegram каналах.\n\n"
        "<b>Режими роботи</b>\n"
        "🔍 <b>Ручний пошук</b> — введи ПІБ і бот пошукає по каналах\n"
        "🟢 <b>Автоматичний live</b> — 2 рази на день (08:00 та 20:00)\n\n"
        "<b>Де записуються результати</b>\n"
        "В таблицю Google Sheets лист 'Mentions' та алерт в чат адміна.",
        parse_mode="HTML"
    )


@router.message(F.text == "◀️ Назад у меню")
async def back_to_main_menu(message: Message):
    """Повернутись у головне меню."""
    from keyboards import main_menu
    await message.answer(
        "📋 Головне меню",
        reply_markup=main_menu()
    )
