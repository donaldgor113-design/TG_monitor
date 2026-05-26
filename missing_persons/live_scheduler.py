"""
APScheduler конфіг для запуску live моніторингу 2 рази на день.

Запускається:
- 08:00 UTC+3 (Київський час)
- 20:00 UTC+3 (Київський час)
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# TODO: додати import apscheduler коли буде готово


def setup_missing_persons_scheduler(bot) -> Optional[object]:
    """
    Налаштувати та запустити APScheduler для live моніторингу.

    Args:
        bot: aiogram Bot об'єкт

    Returns:
        scheduler об'єкт або None якщо помилка

    TODO: Реалізувати коли буде apscheduler встановлено

    Приклад:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler

        scheduler = AsyncIOScheduler(timezone='Europe/Kyiv')
        scheduler.add_job(
            start_missing_live_monitoring,
            trigger='cron',
            hour='8,20',
            minute=0,
            kwargs={'bot': bot}
        )
        scheduler.start()
        return scheduler
    """

    logger.info("Setting up Missing Persons Live Scheduler...")

    try:
        # TODO: реалізувати

        logger.info("✓ Missing Persons scheduler started")
        return None

    except Exception as e:
        logger.error(f"✗ Failed to setup scheduler: {e}", exc_info=True)
        return None


def shutdown_missing_persons_scheduler(scheduler: Optional[object]) -> bool:
    """Зупинити scheduler при завершенні бота."""

    if not scheduler:
        return True

    try:
        # TODO: scheduler.shutdown()
        logger.info("✓ Missing Persons scheduler stopped")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to shutdown scheduler: {e}")
        return False


# Глобальна змінна для scheduler
missing_scheduler: Optional[object] = None
