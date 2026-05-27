import logging
import asyncio
from typing import List, Dict, Set
from telethon.errors import FloodWaitError
from client import userbot
from missing_persons.utils import search_name_in_text, escape_html
from missing_persons.database import check_url_exists

logger = logging.getLogger(__name__)


async def search_in_channel(channel: str, person_names: Dict[str, str],
                           existing_urls: Set[str], limit: int = 50) -> List[Dict]:
    mentions = []
    try:
        async for message in userbot.iter_messages(channel, limit=limit):
            if not message.text:
                continue

            url = f"https://t.me/{channel}/{message.id}"
            if url in existing_urls or check_url_exists(url):
                continue

            for full_name in person_names.keys():
                if search_name_in_text(message.text, full_name):
                    mention = {
                        "pib": full_name,
                        "channel": channel,
                        "message_id": message.id,
                        "url": url,
                        "text": escape_html(message.text),
                        "date": message.date.strftime("%d.%m"),
                        "time": message.date.strftime("%H:%M"),
                        "mention_type": "missing",
                    }
                    mentions.append(mention)
                    logger.info(f"🎯 Знайдено: {full_name} в {channel}")
                    break

    except FloodWaitError as e:
        logger.warning(f"⏸ FloodWait {e.seconds} сек в {channel}")
        if e.seconds < 30:
            await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"❌ Помилка пошуку в {channel}: {e}")

    return mentions


async def search_in_batch(channels: List[str], person_names: Dict[str, str],
                          existing_urls: Set[str], batch_size: int = 5,
                          batch_pause: int = 30, channel_delay: float = 2) -> List[Dict]:
    all_mentions = []

    for i in range(0, len(channels), batch_size):
        batch = channels[i:i + batch_size]
        logger.info(f"📡 Партія {i//batch_size + 1}: обробляю {len(batch)} каналів...")

        batch_mentions = []
        for channel in batch:
            mentions = await search_in_channel(channel, person_names, existing_urls)
            batch_mentions.extend(mentions)
            await asyncio.sleep(channel_delay)

        all_mentions.extend(batch_mentions)

        if i + batch_size < len(channels):
            logger.info(f"⏸ Пауза {batch_pause} сек перед наступною партією...")
            await asyncio.sleep(batch_pause)

    return all_mentions
