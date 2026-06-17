import logging
import asyncio
from typing import List, Dict, Set
from telethon.errors import FloodWaitError
from client import userbot
from missing_persons.utils import search_person_in_text, escape_html, PersonData
from missing_persons.database import check_url_exists

logger = logging.getLogger(__name__)


async def search_in_channel(channel: str, person_names: Dict[str, PersonData],
                           existing_urls: Set[str], limit: int = 700, mention_type: str = "missing") -> List[Dict]:
    mentions = []
    try:
        async for message in userbot.iter_messages(channel, limit=limit):
            if not message.text:
                continue

            url = f"https://t.me/{channel}/{message.id}"
            if url in existing_urls:
                continue

            for full_name, person in person_names.items():
                # Перевіряємо, чи дата публікації після дати коли людина зникла
                pub_date = message.date.strftime("%d.%m.%Y")
                if not person.is_publication_relevant(pub_date):
                    continue

                found, match_detail = search_person_in_text(message.text, person)
                if found:
                    mention = {
                        "pib": full_name,
                        "channel": channel,
                        "message_id": message.id,
                        "url": url,
                        "text": escape_html(message.text),
                        "date": pub_date,
                        "time": message.date.strftime("%H:%M:%S"),
                        "mention_type": mention_type,
                        "match_detail": match_detail,
                    }
                    mentions.append(mention)
                    logger.info(f"🎯 Знайдено: {full_name} ({match_detail}) в {channel} ({pub_date})")
                    break

    except FloodWaitError as e:
        logger.warning(f"⏸ FloodWait {e.seconds} сек в {channel}")
        if e.seconds < 30:
            await asyncio.sleep(e.seconds)
    except Exception as e:
        logger.error(f"❌ Помилка пошуку в {channel}: {e}")

    return mentions


async def search_in_batch(channels: List[str], person_names: Dict[str, PersonData],
                          existing_urls: Set[str], batch_size: int = 5,
                          batch_pause: int = 45, channel_delay: float = 3, mention_type: str = "missing") -> List[Dict]:
    all_mentions = []

    for i in range(0, len(channels), batch_size):
        batch = channels[i:i + batch_size]
        logger.info(f"📡 Партія {i//batch_size + 1}: обробляю {len(batch)} каналів...")

        batch_mentions = []
        for channel in batch:
            mentions = await search_in_channel(channel, person_names, existing_urls, mention_type=mention_type)
            batch_mentions.extend(mentions)
            await asyncio.sleep(channel_delay)

        all_mentions.extend(batch_mentions)

        if i + batch_size < len(channels):
            logger.info(f"⏸ Пауза {batch_pause} сек перед наступною партією...")
            await asyncio.sleep(batch_pause)

    return all_mentions
