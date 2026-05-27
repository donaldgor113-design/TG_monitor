# bot.py
import asyncio
import traceback
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, notify_owners, load_data
from client import userbot
from missing_persons.live_scheduler import init_scheduler, start_scheduler, stop_scheduler

from handlers import admin, calendar, missing_persons_handler
from monitoring import archive, live

bot = Bot(token=BOT_TOKEN)
dp  = Dispatcher(storage=MemoryStorage())

dp.include_router(admin.router)
dp.include_router(calendar.router)
dp.include_router(archive.router)
dp.include_router(live.router)
dp.include_router(missing_persons_handler.router)


async def main():
    await userbot.start()

    d = load_data()

    # ── Ініціалізація scheduler для пошуку зниклих ──
    scheduler = init_scheduler(bot)
    start_scheduler()

    # ── Якщо live був активний до падіння — відновлюємо ──
    if d.get("monitoring") and d.get("live_active_channels") and d.get("live_active_keywords"):
        await notify_owners(bot, "🔄 Бот перезапустився — відновлюю live-моніторинг автоматично...")
        asyncio.create_task(live.start_monitoring(bot, d))

    # ── Запускаємо Telethon polling у фоні ──
    asyncio.create_task(userbot.run_until_disconnected())

    await dp.start_polling(bot)


async def run():
    try:
        await notify_owners(bot, "🟢 Бот запущений і працює!")
        await main()
    except Exception as e:
        err = traceback.format_exc()
        try:
            await notify_owners(
                bot,
                f"🔴 <b>Бот впав!</b>\n\n"
                f"<b>Причина:</b>\n<code>{str(e)}</code>\n\n"
                f"<b>Деталі:</b>\n<code>{err[-2000:]}</code>\n\n"
                f"⏳ Перезапуск через 5 секунд...",
                parse_mode="HTML"
            )
        except Exception:
            pass
        raise


if __name__ == "__main__":
    asyncio.run(run())
