# monitoring/archive.py
import asyncio
import logging
from datetime import datetime, timedelta, timezone


from aiogram import Router, F, types
from telethon.errors import FloodWaitError


from config import MIN_HITS_OLD, is_admin, notify_admins, notify_owners, load_data, save_data, escape_html, get_active_session
from client import userbot
from keyboards import channels_selection_keyboard, keywords_selection_keyboard
from keywords import compare_classifiers, build_legacy_result, classify_post_v2, get_classifier_mode_label


router = Router()
logger = logging.getLogger(__name__)



def _resolve_archive_classification(text: str, active_keywords: list, mode: str) -> tuple[dict, dict | None]:
    if mode == "v2":
        return classify_post_v2(text, active_keywords), None
    if mode == "shadow":
        compared = compare_classifiers(text, active_keywords, min_hits=MIN_HITS_OLD)
        return compared["legacy"], compared["v2"]
    return build_legacy_result(text, active_keywords, min_hits=MIN_HITS_OLD), None



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
@router.message(F.text == "🔍 Пошук по архіву")
async def archive_search_start(msg: types.Message):
    if not is_admin(msg.from_user.id): return
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
        "📡 <b>Крок 1/2 — Вибери канали для пошуку:</b>",
        parse_mode="HTML",
        reply_markup=channels_selection_keyboard(d["channels"], d["arc_active_channels"], "arc")
    )



# ── Канали: toggle / all / none / next ──────────────────
@router.callback_query(F.data.startswith("arc_ch_toggle:"))
async def arc_ch_toggle(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    ch     = callback.data.split("arc_ch_toggle:")[1]
    d      = load_data()
    active = d.get("arc_active_channels", [])
    if ch in active: active.remove(ch)
    else: active.append(ch)
    d["arc_active_channels"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], active, "arc")
    )
    await callback.answer()


@router.callback_query(F.data == "arc_ch_all")
async def arc_ch_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["arc_active_channels"] = d["channels"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], d["arc_active_channels"], "arc")
    )
    await callback.answer("✅ Всі вибрані")


@router.callback_query(F.data == "arc_ch_none")
async def arc_ch_none(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["arc_active_channels"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=channels_selection_keyboard(d["channels"], [], "arc")
    )
    await callback.answer("❌ Всі зняті")


@router.callback_query(F.data == "arc_ch_next")
async def arc_ch_next(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    if not d.get("arc_active_channels"):
        await callback.answer("⚠️ Вибери хоча б один канал!", show_alert=True)
        return
    if not d.get("arc_active_keywords"):
        d["arc_active_keywords"] = d["keywords"].copy()
        save_data(d)
    await callback.message.edit_text(
        "🔑 <b>Крок 2/2 — Вибери ключові слова:</b>",
        parse_mode="HTML",
        reply_markup=keywords_selection_keyboard(d["keywords"], d["arc_active_keywords"], "arc")
    )
    await callback.answer()



# ── Ключові слова: toggle / all / none / start ──────────
@router.callback_query(F.data.startswith("arc_kw_toggle:"))
async def arc_kw_toggle(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    kw     = callback.data.split("arc_kw_toggle:")[1]
    d      = load_data()
    active = d.get("arc_active_keywords", [])
    if kw in active: active.remove(kw)
    else: active.append(kw)
    d["arc_active_keywords"] = active
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], active, "arc")
    )
    await callback.answer()


@router.callback_query(F.data == "arc_kw_all")
async def arc_kw_all(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["arc_active_keywords"] = d["keywords"].copy()
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], d["arc_active_keywords"], "arc")
    )
    await callback.answer("✅ Всі вибрані")


@router.callback_query(F.data == "arc_kw_none")
async def arc_kw_none(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    d["arc_active_keywords"] = []
    save_data(d)
    await callback.message.edit_reply_markup(
        reply_markup=keywords_selection_keyboard(d["keywords"], [], "arc")
    )
    await callback.answer("❌ Всі зняті")


@router.callback_query(F.data == "arc_kw_start")
async def arc_kw_start(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id): return
    d = load_data()
    if not d.get("arc_active_keywords"):
        await callback.answer("⚠️ Вибери хоча б одне слово!", show_alert=True)
        return
    date_from_str = d.get("date_from")
    date_to_str   = d.get("date_to")
    if not date_from_str or not date_to_str:
        await callback.answer("⚠️ Спочатку встанови період!", show_alert=True)
        return

    # ── Перевірка активної сесії ────────────────────────
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
    # ────────────────────────────────────────────────────

    since = datetime.strptime(date_from_str, "%d.%m.%Y").replace(tzinfo=timezone.utc)
    until = datetime.strptime(date_to_str, "%d.%m.%Y").replace(
        hour=23, minute=59, second=59, tzinfo=timezone.utc
    )
    d["archive_running"] = True
    d["active_session_user"] = callback.from_user.id
    save_data(d)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()
    await notify_owners(
        callback.bot,
        f"⏳ Запускаю пошук по архіву...\n"
        f"🧠 Режим: {get_classifier_mode_label(d.get('classifier_mode', 'legacy'))}\n"
        f"📅 Період: <b>{date_from_str}</b> — <b>{date_to_str}</b>\n"
        f"📡 Каналів: {len(d['arc_active_channels'])}\n"
        f"🔑 Слова: {', '.join(d['arc_active_keywords'])}",
        parse_mode="HTML"
    )
    asyncio.create_task(scan_old_posts(callback.bot, since, until, d))



# ── Сканування архіву ───────────────────────────────────
async def scan_old_posts(bot, since, until, d):
    total = 0
    mode = d.get("classifier_mode", "legacy")


    await notify_owners(
        bot,
        f"🔍 Сканую пости з <b>{since.strftime('%d.%m.%Y')}</b> по <b>{until.strftime('%d.%m.%Y')}</b>...",
        parse_mode="HTML"
    )


    for channel in d["arc_active_channels"]:
        try:
            entity = await userbot.get_entity(channel)
            await notify_owners(bot, f"📡 Сканую @{channel}...")


            async for message in userbot.iter_messages(
                entity,
                limit=None,
                offset_date=until + timedelta(seconds=1),
                reverse=False
            ):
                msg_date = message.date.replace(tzinfo=timezone.utc)
                if msg_date < since:
                    break
                if msg_date > until:
                    continue


                text = message.text or message.message or ""
                if not text:
                    continue


                classification, shadow_v2 = _resolve_archive_classification(text, d["arc_active_keywords"], mode)
                if not classification.get("matched"):
                    continue


                username    = getattr(entity, "username", None)
                title       = escape_html(getattr(entity, "title", "Невідомо"))
                subscribers = getattr(entity, "participants_count", "—")
                description = escape_html(getattr(entity, "about", "—") or "—")
                verified    = "✅ Так" if getattr(entity, "verified", False) else "Ні"
                restricted  = "⚠️ Так" if getattr(entity, "restricted", False) else "Ні"
                scam        = "🚨 Так" if getattr(entity, "scam", False) else "Ні"
                url         = f"https://t.me/{username}/{message.id}" if username else "—"
                date_str = message.date.strftime("%d.%m.%Y")
                time_str = message.date.strftime("%H:%M")
                safe_text   = escape_html(text[:600])
                views       = getattr(message, "views", "—") or "—"
                forwards    = getattr(message, "forwards", "—") or "—"
                post_author = escape_html(getattr(message, "post_author", None) or "—")
                has_media   = "📎 Так" if message.media else "Ні"
                replies     = "—"
                if hasattr(message, "replies") and message.replies:
                    replies = str(message.replies.replies)
                matched = classification["main_topic"]
                sheet_name = classification.get("sheet_name")
                found_forms = classification.get("found_forms", [])
                score = classification.get("score", 0)
                confidence = classification.get("confidence", "—")
                shadow_note = _format_shadow_note(classification, shadow_v2) if mode == "shadow" else ""


                alert = (
                    f"📌 <b>Старий пост знайдено!</b>\n\n"
                    f"🧠 <b>Режим:</b> <code>{get_classifier_mode_label(mode)}</code>\n"
                    f"🔑 <b>Ключове слово:</b> <code>{matched}</code>\n"
                    f"📂 <b>Вкладка:</b> <code>{sheet_name or '—'}</code>\n"
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
                await notify_admins(bot, alert, parse_mode="HTML")
                total += 1
                await asyncio.sleep(0.3)


        except FloodWaitError as e:
            await notify_owners(bot, f"⏳ Telegram просить зачекати {e.seconds} сек...")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            await notify_owners(bot, f"⚠️ Помилка з каналом @{channel}: {e}")


    summary = f"✅ Сканування завершено! Знайдено постів: {total}"
    await notify_owners(bot, summary)

    d_final = load_data()
    d_final["archive_running"] = False
    d_final["active_session_user"] = None
    save_data(d_final)