import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import MISSING_PERSONS_SHEET_ID
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


def detect_status_from_text(text: str) -> str:
    """Аналізує текст і визначає статус особи."""
    text_lower = text.lower()

    if any(word in text_lower for word in ["знайдено", "знаходиться", "виявлено", "знайшли", "в безпеці", "живий", "живий тепер"]):
        return "знайдено і в безпеці"
    elif any(word in text_lower for word in ["полон", "в полоні", "захоплен", "в полоні", "полоняник"]):
        return "полон"
    elif any(word in text_lower for word in ["загинув", "помер", "померла", "загибель", "убит", "убита", "убитий", "вбитий"]):
        return "загинув"
    elif any(word in text_lower for word in ["безвісти", "зникав", "не знайдено", "невідомо де", "невідомих місцеперебування"]):
        return "безвісти зниклий"
    else:
        return ""


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
            if len(row) >= 6:
                surname = row[1].strip() if len(row) > 1 else ""
                name = row[2].strip() if len(row) > 2 else ""
                patronymic = row[3].strip() if len(row) > 3 else ""
                status = row[5].strip().lower() if len(row) > 5 else ""

                pib = f"{surname} {name}".strip()
                if patronymic:
                    pib = f"{pib} {patronymic}"

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
            pib = mention.get("pib", "").strip()
            parts = pib.split()
            surname = parts[0] if len(parts) > 0 else ""
            name = parts[1] if len(parts) > 1 else ""
            patronymic = parts[2] if len(parts) > 2 else ""

            text = mention.get("text", "")[:300]
            status = detect_status_from_text(text)

            row = [
                "",  # Колона A: № (автоматично)
                surname,
                name,
                patronymic,
                status,  # Статус, визначений автоматично
                mention.get("channel", ""),
                mention.get("date", ""),
                mention.get("time", ""),
                text,
                mention.get("url", ""),
            ]
            ws.append_row(row)
            logger.info(f"✅ Запис додано: {pib} в {mention['channel']} | Статус: {status or 'не визначено'}")

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
                if len(row) >= 10:
                    url = row[9].strip()  # Колона J (індекс 9) - URL
                    if url:
                        urls.add(url)
        logger.info(f"✅ Завантажено {len(urls)} URL з листа Mentions")
        return urls
    except Exception as e:
        logger.error(f"❌ Помилка завантаження URLs: {e}")
        return set()
