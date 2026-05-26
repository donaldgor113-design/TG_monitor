"""
Синхронізація результатів пошуку з Google Sheets.
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# TODO: додати import gspread та інші залежності коли буде готово


async def append_mention_to_sheets(
    mention: Dict[str, str],
    sheet_name: str = "Mentions"
) -> bool:
    """
    Додати запис про знайдену згадку в Google Sheets.

    Args:
        mention: {
            "pib": "Карпенко сергій",
            "channel": "agumova_chat",
            "date": "25.05",
            "time": "14:30",
            "url": "https://t.me/...",
            "text": "Карпенко виявлений...",
            "type": "missing" | "found" | "deceased" | "returned"
        }
        sheet_name: назва листа в Sheets

    Returns:
        True якщо успішно, False якщо помилка

    TODO: Реалізувати з gspread
    """

    logger.info(f"Appending mention to Sheets: {mention['pib']} in {mention['channel']}")

    # TODO: реалізувати

    return True


async def get_mentions_from_sheets(
    sheet_name: str = "Mentions",
    limit: int = 100
) -> List[Dict[str, str]]:
    """
    Отримати останні записи з листа Mentions.

    Args:
        sheet_name: назва листа
        limit: максимум записів для повернення

    Returns:
        список записів

    TODO: Реалізувати з gspread
    """

    logger.info(f"Loading mentions from Sheets (limit={limit})")

    # TODO: реалізувати

    return []


async def check_url_exists_in_sheets(
    message_url: str,
    sheet_name: str = "Mentions"
) -> bool:
    """
    Перевірити чи URL вже у таблиці (дедублікація).

    Args:
        message_url: посилання на пост (https://t.me/channel/123)
        sheet_name: назва листа

    Returns:
        True якщо URL існує, False якщо не існує

    TODO: Реалізувати з gspread
    """

    logger.info(f"Checking if URL exists: {message_url}")

    # TODO: реалізувати

    return False


class GoogleSheetsCache:
    """
    Кеш для данних з Google Sheets.
    Оновлюється кожні 5 хвилин щоб не перегруджувати API.
    """

    def __init__(self, cache_timeout_minutes: int = 5):
        self.cache_timeout_minutes = cache_timeout_minutes
        self.last_update: Optional[datetime] = None
        self.channels_cache: List[str] = []
        self.persons_cache: List[Dict[str, str]] = []

    async def get_channels(self, force_refresh: bool = False) -> List[str]:
        """
        Отримати список каналів з кешу або з Sheets.

        Args:
            force_refresh: перезавантажити з Sheets навіть якщо кеш свіжий

        Returns:
            список username каналів
        """

        if not self._is_cache_valid() or force_refresh:
            logger.info("Refreshing channels cache from Sheets...")
            # TODO: завантажити з Sheets
            self.last_update = datetime.now()

        return self.channels_cache

    async def get_persons(self, force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Отримати список осіб зі статусом missing з кешу або з Sheets.

        Args:
            force_refresh: перезавантажити з Sheets

        Returns:
            список осіб
        """

        if not self._is_cache_valid() or force_refresh:
            logger.info("Refreshing persons cache from Sheets...")
            # TODO: завантажити з Sheets з фільтром по статусу "missing"
            self.last_update = datetime.now()

        return self.persons_cache

    def _is_cache_valid(self) -> bool:
        """Перевірити чи кеш ще свіжий."""
        if self.last_update is None:
            return False

        age = datetime.now() - self.last_update
        return age.total_seconds() < (self.cache_timeout_minutes * 60)

    def clear_cache(self):
        """Очистити кеш."""
        self.channels_cache = []
        self.persons_cache = []
        self.last_update = None


# Глобальний кеш для uso у всьому проекті
sheets_cache = GoogleSheetsCache(cache_timeout_minutes=5)
