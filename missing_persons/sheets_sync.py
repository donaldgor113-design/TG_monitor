import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import MISSING_PERSONS_SHEET_ID
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


def get_spreadsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(MISSING_PERSONS_SHEET_ID)


def load_missing_persons() -> Dict[str, str]:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Missing Persons")
        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            logger.info("📋 Лист 'Missing Persons' порожній")
            return {}

        persons = {}
        for row in all_values[1:]:
            if len(row) >= 3:
                pib = row[0].strip()
                status = row[2].strip().lower()
                if pib and status == "missing":
                    persons[pib] = status
        logger.info(f"📋 Завантажено {len(persons)} осіб зі статусом 'missing'")
        return persons
    except Exception as e:
        logger.error(f"❌ Помилка завантаження Missing Persons: {e}")
        return {}


def load_missing_channels() -> List[str]:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Channels Missing")
        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            logger.info("📡 Лист 'Channels Missing' порожній")
            return []

        channels = []
        for row in all_values[1:]:
            if len(row) >= 2:
                url = row[0].strip()
                status = row[1].strip().lower()
                if url and status == "active":
                    channel_username = url.replace("https://t.me/", "").replace("@", "")
                    channels.append(channel_username)
        logger.info(f"📡 Завантажено {len(channels)} активних каналів")
        return channels
    except Exception as e:
        logger.error(f"❌ Помилка завантаження Channels Missing: {e}")
        return []


def append_to_mentions(mentions: List[Dict]):
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Mentions")

        for mention in mentions:
            row = [
                "",  # Колона A: № (автоматично нумерується)
                mention.get("pib", ""),
                mention.get("channel", ""),
                mention.get("date", ""),
                mention.get("time", ""),
                mention.get("text", "")[:300],
                mention.get("url", ""),
                mention.get("mention_type", "missing"),
            ]
            ws.append_row(row)
            logger.info(f"✅ Запис додано: {mention['pib']} в {mention['channel']}")

        return True
    except Exception as e:
        logger.error(f"❌ Помилка запису в Mentions: {e}")
        return False


def load_all_existing_urls() -> Set[str]:
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Mentions")
        all_values = ws.get_all_values()

        urls = set()
        if len(all_values) > 1:
            for row in all_values[1:]:
                if len(row) >= 7:
                    url = row[6].strip()  # Колона G (індекс 6) через наявність колони № в A
                    if url:
                        urls.add(url)
        logger.info(f"✅ Завантажено {len(urls)} URL з листа Mentions")
        return urls
    except Exception as e:
        logger.error(f"❌ Помилка завантаження URLs: {e}")
        return set()
