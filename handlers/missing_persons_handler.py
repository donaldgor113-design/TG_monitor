# handlers/missing_persons_handler.py
import logging
import asyncio
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from config import is_admin, load_data, save_data, notify_owners
from keyboards import main_menu, missing_persons_menu, management_menu
from missing_persons.sheets_sync import load_missing_persons, load_missing_channels, load_all_existing_urls, append_to_mentions, detect_status_from_text
from missing_persons.search_engine import search_in_batch
from missing_persons.database import save_mention, get_mentions_count
from missing_persons.utils import PersonData
from states import SearchMissingPerson

router = Router()
logger = logging.getLogger(__name__)


# ── Меню пошуку зниклих ─────────────────────────────────
@router.message(F.text == "🔍 Пошук за ПІБ")
async def ask_for_pib(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id): return
    await state.set_state(SearchMissingPerson.waiting)
    await msg.answer(
        "🔍 <b>Архівний пошук за ПІБ</b>\n\n"
        "Введи ім'я особи для пошуку (напр: Петренко Петро):",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(SearchMissingPerson.waiting)
async def search_pib(msg: types.Message, state: FSMContext):
    if not is_admin(msg.from_user.id):
        await state.clear()
        return

    pib = msg.text.strip()
    if not pib:
        await msg.answer("❌ Введи ПІБ!", reply_markup=missing_persons_menu())
        await state.clear()
        return

    d = load_data()
    await msg.answer(
        f"🔍 <b>Шукаю:</b> {pib}\n\n"
        f"⏳ Це може зайняти 2-5 хвилин...",
        parse_mode="HTML"
    )

    try:
        channels = load_missing_channels()
        existing_urls = load_all_existing_urls()

        if not channels:
            await msg.answer(
                "⚠️ Немає активних каналів для пошуку.\n"
                "Додай канали в Google Sheets 'Channels Missing'",
                reply_markup=missing_persons_menu()
            )
            await state.clear()
            return

        # Пошук з таймаутом
        parts = pib.split()
        person = PersonData(
            surname=parts[0] if len(parts) > 0 else "",
            name=parts[1] if len(parts) > 1 else "",
            patronymic=parts[2] if len(parts) > 2 else "",
            status="missing"
        )
        persons = {pib: person}
        try:
            mentions = await asyncio.wait_for(
                search_in_batch(channels, persons, existing_urls),
                timeout=600  # 10 хвилин максимум
            )
        except asyncio.TimeoutError:
            await msg.answer(
                "⏱ <b>Таймаут пошуку</b>\n\n"
                "Пошук занадто довгий. Спробуй пізніше або введи менш популярне ім'я.",
                parse_mode="HTML",
                reply_markup=missing_persons_menu()
            )
            await state.clear()
            return

        if mentions:
            # Запис в Google Sheets
            append_to_mentions(mentions)
            for mention in mentions:
                save_mention(
                    pib=mention["pib"],
                    channel=mention["channel"],
                    message_id=mention["message_id"],
                    url=mention["url"],
                    text=mention["text"],
                    post_date=mention["date"],
                    post_time=mention["time"],
                    mention_type="manual_search"
                )

            result_text = (
                f"🎯 <b>Знайдено {len(mentions)} згадок про {pib}:</b>\n"
                f"📡 Перевірено каналів: <b>{len(channels)}</b> (до 300 публікацій кожен)\n\n"
            )
            for i, m in enumerate(mentions[:5], 1):
                channel = m['channel']
                status = detect_status_from_text(m['text'])
                status_str = status if status else "не визначено"
                short_text = m['text'][:200].replace('\n', ' ')
                result_text += (
                    f"{i}. 📢 <a href=\"https://t.me/{channel}\">@{channel}</a> | {m['date']} {m['time']}\n"
                    f"   🔗 <a href=\"{m['url']}\">Посилання на публікацію</a>\n"
                    f"   🏷 Статус: <b>{status_str}</b>\n"
                    f"   📝 {short_text}...\n\n"
                )
            if len(mentions) > 5:
                result_text += f"+ ще {len(mentions) - 5} результатів\n\n"

            result_text += "✅ Всі результати записані в Google Sheets 'Mentions'"

            await msg.answer(result_text, parse_mode="HTML", reply_markup=missing_persons_menu())
        else:
            await msg.answer(
                f"❌ Не знайдено згадок про <b>{pib}</b>",
                parse_mode="HTML",
                reply_markup=missing_persons_menu()
            )

    except Exception as e:
        logger.error(f"❌ Помилка пошуку: {e}")
        await msg.answer(
            f"❌ Помилка під час пошуку:\n<code>{str(e)}</code>",
            parse_mode="HTML",
            reply_markup=missing_persons_menu()
        )

    await state.clear()


# ── Статистика ──────────────────────────────────────────
@router.message(F.text == "📊 Статистика зниклих")
async def show_stats(msg: types.Message):
    if not is_admin(msg.from_user.id): return

    try:
        persons = load_missing_persons()
        channels = load_missing_channels()
        mentions_count = get_mentions_count()

        text = (
            f"📊 <b>Статистика пошуку зниклих</b>\n\n"
            f"👥 <b>Осіб зі статусом 'missing':</b> {len(persons)}\n"
            f"📡 <b>Активних каналів:</b> {len(channels)}\n"
            f"🎯 <b>Всього згадок:</b> {mentions_count}\n\n"
            f"🔄 Live моніторинг: кожен день о 08:00 та 20:00"
        )
        await msg.answer(text, parse_mode="HTML", reply_markup=missing_persons_menu())
    except Exception as e:
        logger.error(f"❌ Помилка статистики: {e}")
        await msg.answer(
            "❌ Помилка під час завантаження статистики",
            reply_markup=missing_persons_menu()
        )


# ── Інформація ──────────────────────────────────────────
@router.message(F.text == "ℹ️ Інформація")
async def show_info(msg: types.Message):
    if not is_admin(msg.from_user.id): return

    text = (
        "ℹ️ <b>Про функцію пошуку зниклих</b>\n\n"
        "<b>Як це працює:</b>\n"
        "🔍 <b>Архівний пошук:</b> шукаємо за ПІБ в архівах каналів (до 500 постів)\n"
        "🔄 <b>Live моніторинг:</b> автоматична перевірка 2 рази на день (08:00, 20:00)\n\n"
        "<b>Де керувати даними:</b>\n"
        "📄 Google Sheets 'Channels Missing' — список каналів (адміни керують)\n"
        "📄 Google Sheets 'Missing Persons' — список осіб (адміни керують)\n"
        "📄 Google Sheets 'Mentions' — результати пошуку (заповнюється автоматично)\n\n"
        "<b>Результати:</b>\n"
        "✅ Кожна знайдена згадка записується в Google Sheets\n"
        "✅ Адміни отримують алерти про важливі знахідки"
    )
    await msg.answer(text, parse_mode="HTML", reply_markup=missing_persons_menu())
