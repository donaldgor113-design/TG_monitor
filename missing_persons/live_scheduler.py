import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from missing_persons.sheets_sync import (
    load_missing_persons, load_missing_channels, append_to_mentions, load_all_existing_urls
)
from missing_persons.search_engine import search_in_batch
from missing_persons.database import save_mention

logger = logging.getLogger(__name__)
scheduler = None


async def run_live_search(bot=None):
    logger.info("🔍 Запуск live пошуку зниклих осіб...")

    persons = load_missing_persons()
    channels = load_missing_channels()
    existing_urls = load_all_existing_urls()

    if not persons or not channels:
        logger.warning("⚠️ Немає осіб або каналів для пошуку")
        if bot:
            from config import get_owner_ids
            for owner_id in get_owner_ids():
                try:
                    await bot.send_message(owner_id, "⚠️ Пошук зниклих: немає осіб або каналів для пошуку")
                except:
                    pass
        return

    logger.info(f"📊 Шукаю {len(persons)} осіб в {len(channels)} каналах...")

    mentions = await search_in_batch(channels, persons, existing_urls)

    if mentions:
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
                mention_type=mention["mention_type"]
            )

        if bot:
            from config import get_owner_ids
            text = f"🎯 <b>Live пошук зниклих</b>\n\nЗнайдено {len(mentions)} згадок:\n"
            for m in mentions[:5]:
                text += f"• {m['pib']} в @{m['channel']}\n"
            if len(mentions) > 5:
                text += f"+ ще {len(mentions) - 5}..."

            for owner_id in get_owner_ids():
                try:
                    await bot.send_message(owner_id, text, parse_mode="HTML")
                except Exception as e:
                    logger.error(f"❌ Помилка відправки алерту: {e}")
    else:
        logger.info("✅ Пошук завершено. Нових згадок не знайдено.")


def init_scheduler(bot=None):
    global scheduler
    if scheduler is None:
        scheduler = AsyncIOScheduler(timezone='Europe/Kyiv')
        scheduler.add_job(
            run_live_search,
            trigger='cron',
            hour='8,20',
            minute=0,
            args=[bot],
            id='missing_persons_live',
            name='Missing Persons Live Search'
        )
        logger.info("✅ Scheduler інініціалізований (08:00, 20:00)")
    return scheduler


def start_scheduler():
    global scheduler
    if scheduler and not scheduler.running:
        scheduler.start()
        logger.info("✅ Scheduler запущений")


def stop_scheduler():
    global scheduler
    if scheduler and scheduler.running:
        scheduler.shutdown()
        logger.info("⏹ Scheduler зупинений")
