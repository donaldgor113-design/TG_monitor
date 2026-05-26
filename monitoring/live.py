# monitoring/live.py
import asyncio
import logging
from aiogram import Router, F, types
from telethon.errors import FloodWaitError

from config import ALERT_CHANNEL, MIN_HITS_NEW, is_admin, is_owner, notify_admins, notify_owners, load_data, save_data, escape_html, get_active_session
from client import userbot
from keyboards import channels_selection_keyboard, keywords_selection_keyboard, main_menu
from keywords import compare_classifiers, build_legacy_result, classify_post_v2, get_classifier_mode_label
from sheets import get_spreadsheet, load_all_existing_urls, append_to_sheet

router = Router()
logger = logging.getLogger(__name__)
_polling_task = None

def _stop_polling():
    global _polling_task
    if _polling_task is not None:
        _polling_task.cancel()
        _polling_task = None

def _resolve_live_classification(text: str, active_keywords: list, mode: str) -> tuple[dict, dict | None]:
    if mode == "v2":
        return classify_post_v2(text, active_keywords), None
    if mode == "shadow":
        compared = compare_classifiers(text, active_keywords, min_hits=MIN_HITS_NEW)
        return compared["legacy"], compared["v2"]
    return build_legacy_result(text, active_keywords, min_hits=MIN_HITS_NEW), None

def _format_shadow_note(legacy_result: dict, v2_result: dict | None) -> str:
    if not v2_result:
        return ""
    legacy_topic = legacy_result.get("main_topic") or "—"
    v2_topic = v2_result.get("main_topic") or "—"
    if legacy_topic == v2_topic:
        return (
            "\n🧪 <b>Shadow V2:</b> "
            f"{v2_topic} | score {v2_result.get('score', 0)} | "
            f"{', '.join(v2_result.get('found_forms', [])[:4]) or 'без форм'}"
        )
    return (
        "\n🧪 <b>Shadow V2 відрізняється:</b> "
        f"{v2_topic} | score {v2_result.get('score', 0)} | "
        f"{', '.join(v2_result.get('found_forms', [])[:4]) or 'без форм'}"
    )

# ── Крок 1 — вибір каналів ──────────────────────────────
@router.message(F.text == "🟢 Моніторинг live")
async def live_monitoring_start(msg: types.Message):
    if not is_admin(msg.from_user.id): return
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
        "📡 <b>Крок 1/2 — Вибери канали для моніторингу:</b>",
        parse_mode="HTML",
        reply_markup=channels_selection_keyboard(d["channels"], d["live_active_channels"], "live")
    )

@router.callback_query(F.data.startswith("live_ch_toggle:"))
async def live_ch_toggle(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    ch     = callback.data.split("live_ch_toggle:")[1]
    d      = load_data()
    active = d.get("live_active_channels", [])
    if ch in active: active.remove(ch)
    else: active.append(ch)
    d["live_active_channels"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], active, "live")
    )
    await callback.answer()

@router.callback_query(F.data == "live_ch_all")
async def live_ch_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["live_active_channels"] = d["channels"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], d["live_active_channels"], "live")
    )
    await callback.answer("✅ Всі вибрані")

@router.callback_query(F.data == "live_ch_none")
async def live_ch_none(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["live_active_channels"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], [])
    )
    await callback.answer("❌ Всі зняті")

@router.callback_query(F.data == "live_ch_next")
async def live_ch_next(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    if not d.get("live_active_channels"):
        await callback.answer("⚠️ Вибери хоча б один канал!", show_alert=True)
        return
    if not d.get("live_active_keywords"):
        d["live_active_keywords"] = d["keywords"].copy()
        save_data(d)
    await callback.message.edit_text(
        "🔑 <b>Крок 2/2 — Вибери ключові слова:</b>",
        parse_mode="HTML",
        reply_markup=keywords_selection_keyboard(d["keywords"], d["live_active_keywords"], "live")
    )
    await callback.answer()

@router.callback_query(F.data.startswith("live_kw_toggle:"))
async def live_kw_toggle(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    kw     = callback.data.split("live_kw_toggle:")[1]
    d      = load_data()
    active = d.get("live_active_keywords", [])
    if kw in active: active.remove(kw)
    else: active.append(kw)
    d["live_active_keywords"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], active, "live")
    )
    await callback.answer()

@router.callback_query(F.data == "live_kw_all")
async def live_kw_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["live_active_keywords"] = d["keywords"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], d["live_active_keywords"], "live")
    )
    await callback.answer("✅ Всі вибрані")

@router.callback_query(F.data == "live_kw_none")
async def live_kw_none(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["live_active_keywords"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], [])
    )
    await callback.answer("❌ Всі зняті")

@router.callback_query(F.data == "live_kw_start")
async def live_kw_start(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    if not d.get("live_active_keywords"):
        await callback.answer("⚠️ Вибери хоча б одне слово!", show_alert=True)
        return

    session = get_active_session(d)
    if session and session["user_id"] != callback.from_user.id:
        stype = "🔴 Live" if session["type"] == "live" else "🗂 Архів"
        await callback.answer(
            f"{stype} вже запущено користувачем {session['user_id']}\n"
            f"📡 Каналів: {session['channels']}\n"
            f"🔑 Ключів: {session['keywords']}",
            show_alert=True
        )
        return

    d["monitoring"] = True
    d["active_session_user"] = callback.from_user.id
    save_data(d)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await notify_owners(
        callback.bot,
        f"🟢 Запускаю моніторинг live...\n"
        f"🧠 Режим: {get_classifier_mode_label(d.get('classifier_mode', 'legacy'))}\n"
        f"📡 Каналів: {len(d['live_active_channels'])}\n"
        f"🔑 Слова: {', '.join(d['live_active_keywords'])}",
        parse_mode="HTML"
    )
    asyncio.create_task(start_monitoring(callback.bot, d))

@router.message(F.text == "⏹ Стоп")
async def stop_cmd(msg: types.Message):
    if not is_admin(msg.from_user.id): return
    d = load_data()
    d["monitoring"] = False
    d["active_session_user"] = None
    save_data(d)
    _stop_polling()
    await msg.answer("🔴 Моніторинг зупинено.", reply_markup=main_menu(is_owner=is_owner(msg.from_user.id)))

async def save_to_sheet_background(spreadsheet, matched, channel, date_str, time_str, url, text, keyword1, keywords):
    try:
        logger.info(f"📊 Починаю запис: channel={channel}, url={url}, keyword1={keyword1}")
        result = append_to_sheet(spreadsheet, matched, channel, date_str, time_str, url, text, keyword1=keyword1, keywords=keywords)
        if result:
            logger.info(f"✅ Успішно записано в таблицю: {url}")
        else:
            logger.warning(f"⚠️ append_to_sheet повернув False: {url}")
    except Exception as e:
        logger.error(f"❌ Помилка запису в таблицю: {e}", exc_info=True)

async def start_monitoring(bot, d: dict):
    global _polling_task

    _stop_polling()

    try:
        spreadsheet   = get_spreadsheet()
        existing_urls = load_all_existing_urls(spreadsheet)
    except Exception as e:
        await notify_owners(bot, f"⚠️ Google Sheets помилка:\n<code>{str(e)}</code>", parse_mode="HTML")
        spreadsheet   = None
        existing_urls = {}

    # Отримуємо Entity ID каналів
    chat_entities = {}
    unique_channels = list(dict.fromkeys(d["live_active_channels"]))
    logger.info(f"🔄 Отримую Entity ID для {len(unique_channels)} каналів")
    for channel in unique_channels:
        try:
            entity = await userbot.get_entity(channel)
            chat_entities[channel] = entity
            logger.info(f"✅ {channel} -> Entity ID {entity.id}")
        except Exception as e:
            logger.error(f"❌ Помилка для {channel}: {str(e)}")

    if not chat_entities:
        await notify_owners(bot, "🚨 Не вдалось отримати Entity ID каналів!")
        return

    # Ініціалізуємо last_message_ids - установлюємо на останню публікацію без обробки
    if "last_message_ids" not in d:
        d["last_message_ids"] = {}
        logger.info("📌 Ініціалізація last_message_ids для кожного каналу")
        for channel_name, entity in chat_entities.items():
            try:
                async for message in userbot.iter_messages(entity, limit=1):
                    d["last_message_ids"][str(entity.id)] = message.id
                    logger.info(f"✅ {channel_name}: установлено last_id = {message.id}")
                    break
            except Exception as e:
                logger.warning(f"⚠️ Помилка ініціалізації {channel_name}: {e}")
    save_data(d)

    async def polling_loop():
        while True:
            try:
                d_cur = load_data()
                if not d_cur.get("monitoring"):
                    logger.info("ℹ️ Моніторинг вимкнений, зупиняю polling")
                    break

                for channel_name, entity in chat_entities.items():
                    try:
                        last_id = d_cur.get("last_message_ids", {}).get(str(entity.id), 0)
                        logger.info(f"🔍 Перевіряю {channel_name}, останній ID: {last_id}")

                        async for message in userbot.iter_messages(entity, limit=5):
                            if message.id <= last_id:
                                continue

                            text = message.text or message.message or ""
                            if not text:
                                continue

                            mode = d_cur.get("classifier_mode", "legacy")
                            classification, shadow_v2 = _resolve_live_classification(text, d_cur["live_active_keywords"], mode)

                            if not classification.get("matched"):
                                continue

                            logger.info(f"✅ Знайдено: {channel_name} - {text[:50]}")

                            try:
                                username = getattr(entity, "username", None)
                                title = escape_html(getattr(entity, "title", "Невідомо"))
                                subscribers = getattr(entity, "participants_count", "—")
                                description = escape_html(getattr(entity, "about", "—") or "—")
                                verified = "✅ Так" if getattr(entity, "verified", False) else "Ні"
                                restricted = "⚠️ Так" if getattr(entity, "restricted", False) else "Ні"
                                scam = "🚨 Так" if getattr(entity, "scam", False) else "Ні"
                                url = f"https://t.me/{username}/{message.id}" if username else "—"
                                date_str = message.date.strftime("%d.%m.%Y")
                                time_str = message.date.strftime("%H:%M")
                                safe_text = escape_html(text[:600])
                                views = getattr(message, "views", "—") or "—"
                                forwards = getattr(message, "forwards", "—") or "—"
                                post_author = escape_html(getattr(message, "post_author", None) or "—")
                                has_media = "📎 Так" if message.media else "Ні"
                                replies = "—"
                                if hasattr(message, "replies") and message.replies:
                                    replies = str(message.replies.replies)

                                matched = classification["main_topic"]
                                sheet_name = classification.get("sheet_name")
                                found_forms = classification.get("found_forms", [])
                                primary_form = classification.get("primary_form") or (found_forms[0] if found_forms else matched)
                                other_topics = classification.get("other_topics", [])
                                other_topics_str = ", ".join(other_topics)
                                score = classification.get("score", 0)
                                confidence = classification.get("confidence", "—")
                                shadow_note = _format_shadow_note(classification, shadow_v2) if mode == "shadow" else ""

                                alert = (
                                    f"🔔 <b>Новий пост знайдено!</b>\n\n"
                                    f"🧠 <b>Режим:</b> <code>{get_classifier_mode_label(mode)}</code>\n"
                                    f"🔑 <b>Ключове слово:</b> <code>{matched}</code>\n"
                                    f"📂 <b>Вкладка:</b> <code>{sheet_name or '—'}</code>\n"
                                    f"🪤 <b>Спрацювала форма:</b> {primary_form or '—'}\n"
                                    f"🧩 <b>Інші теми:</b> {other_topics_str or '—'}\n"
                                    f"📊 <b>Score:</b> {score}\n"
                                    f"🎯 <b>Confidence:</b> {confidence}\n"
                                    f"🔎 <b>Знайдені форми:</b> {', '.join(found_forms[:6]) or '—'}"
                                    f"{shadow_note}\n\n"
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

                                if sheet_name:
                                    existing_urls.setdefault(sheet_name, set()).add(url)

                                if ALERT_CHANNEL:
                                    await bot.send_message(int(ALERT_CHANNEL), alert, parse_mode="HTML")
                                else:
                                    await notify_admins(bot, alert, parse_mode="HTML")

                                logger.info(f"📝 Записую в таблицю. URL: {url}, Sheet: {sheet_name}, Spreadsheet: {spreadsheet is not None}")
                                if spreadsheet and sheet_name:
                                    logger.info(f"✅ Запускаю запис у фоні для {sheet_name}")
                                    asyncio.create_task(save_to_sheet_background(
                                        spreadsheet, matched,
                                        f"@{username or 'unknown'}", date_str, time_str, url, text,
                                        primary_form or "", other_topics_str
                                    ))
                                else:
                                    logger.warning(f"⚠️ Не можу записати: spreadsheet={spreadsheet is not None}, sheet_name={sheet_name}")

                                # Оновлюємо last_message_id
                                d_cur["last_message_ids"][str(entity.id)] = message.id
                                save_data(d_cur)

                            except Exception as e:
                                logger.error(f"Помилка при обробці повідомлення: {e}")

                    except FloodWaitError as e:
                        logger.info(f"⏳ Flood wait {e.seconds} сек")
                        await asyncio.sleep(e.seconds)
                    except Exception as e:
                        logger.error(f"Помилка з каналом {channel_name}: {e}")

                await asyncio.sleep(60)  # Чекаємо 1 хвилину

            except Exception as e:
                logger.error(f"Помилка в polling loop: {e}", exc_info=True)
                await asyncio.sleep(10)

    _polling_task = asyncio.create_task(polling_loop())
    await notify_owners(bot, "🟢 Live-моніторинг запущений (перевіка кожну хвилину)")
