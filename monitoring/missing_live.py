"""
Live моніторинг зниклих осіб — запускається 2 рази на день (08:00, 20:00).
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


async def load_missing_persons_from_sheets() -> List[Dict[str, str]]:
    """
    Завантажити список осіб зі статусом "missing" з Google Sheets.

    Returns:
        [
            {"name": "Карпенко сергій", "status": "missing", "note": "29 років"},
            ...
        ]

    TODO: Реалізувати коли буде gspread
    """
    logger.info("Loading missing persons from Google Sheets...")
    # TODO: читати лист "Missing Persons"
    return []


async def load_channels_from_sheets() -> List[str]:
    """
    Завантажити список активних каналів з Google Sheets.

    Returns:
        ["agumova_chat", "poloneniukr", "UkrRFpl", ...]

    TODO: Реалізувати коли буде gspread
    """
    logger.info("Loading channels from Google Sheets...")
    # TODO: читати лист "Channels Missing"
    return []


async def search_in_batch(
    channels: List[str],
    persons: List[Dict[str, str]],
    batch_size: int = 5,
    delay_between_channels: float = 2.0,
    delay_between_batches: float = 30.0
) -> Dict[str, list]:
    """
    Шукає осіб у батчі каналів.

    Args:
        channels: список username каналів
        persons: список осіб зі статусом missing
        batch_size: скільки каналів обробляти одночасно
        delay_between_channels: затримка між каналами (2 сек)
        delay_between_batches: затримка між батчами (30 сек)

    Returns:
        {
            "found": [{"person": "...", "channel": "...", "url": "..."}],
            "errors": ["FloodWaitError in agumova_chat"],
            "processed": 20
        }

    TODO: Реалізувати пошук коли буде telethon + gspread
    """

    logger.info(
        f"Starting batch search: {len(channels)} channels, "
        f"{len(persons)} persons, batch_size={batch_size}"
    )

    results = {
        "found": [],
        "errors": [],
        "processed": 0
    }

    # TODO: Реалізувати логіку батч-обробки каналів
    # 1. Розділити channels на батчи по batch_size
    # 2. Для кожного батча:
    #    a. Отримати останні 50 постів з кожного каналу
    #    b. Шукати ПІБ у тексті постів
    #    c. Якщо знайдено — записати в БД і Sheets
    #    d. Обробити FloodWaitError
    #    e. Чекати delay_between_batches перед наступним батчем

    logger.info(f"Batch search completed. Found: {len(results['found'])}")

    return results


async def start_missing_live_monitoring(bot, d: dict):
    """
    Основна функція live моніторингу.
    Запускається за розписанням 08:00 та 20:00.

    Args:
        bot: aiogram Bot об'єкт
        d: monitor_data.json словник

    TODO: Реалізувати коли буде готова інтеграція
    """

    logger.info("🟢 Starting Missing Persons Live Monitoring")

    try:
        # 1. Завантажити дані
        persons = await load_missing_persons_from_sheets()
        channels = await load_channels_from_sheets()

        if not persons or not channels:
            logger.warning("No persons or channels to search")
            return

        logger.info(f"Found {len(persons)} persons and {len(channels)} channels")

        # 2. Шукати по батчах
        results = await search_in_batch(
            channels=channels,
            persons=persons,
            batch_size=5,
            delay_between_channels=2.0,
            delay_between_batches=30.0
        )

        # 3. Надіслати адміну алерт про результати
        if results["found"]:
            message = (
                f"🟢 <b>Missing Persons Live Search Results</b>\n\n"
                f"✓ Found: {len(results['found'])} mentions\n"
                f"✓ Processed: {results['processed']} messages\n"
                f"⚠️ Errors: {len(results['errors'])}"
            )

            # TODO: notify_admins(bot, message, parse_mode="HTML")

        logger.info(f"✓ Missing persons live monitoring completed")

    except Exception as e:
        logger.error(f"✗ Missing persons live monitoring failed: {e}", exc_info=True)
        # TODO: notify_owners(bot, f"🔴 Missing persons monitoring error: {e}")


# Приклад використання (для тестування вручну)
if __name__ == "__main__":
    import asyncio

    async def test():
        logger.basicConfig(level=logging.INFO)

        # Тест без реальних даних (заглушка)
        results = await search_in_batch(
            channels=["test_channel"],
            persons=[{"name": "Петренко", "status": "missing"}],
            batch_size=5
        )
        print(f"Test results: {results}")

    # asyncio.run(test())
