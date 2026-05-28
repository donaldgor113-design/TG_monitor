import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import MISSING_PERSONS_SHEET_ID
from typing import List, Dict, Set

logger = logging.getLogger(__name__)


def detect_status_from_text(text: str) -> str:
    text_lower = text.lower()

    if any(word in text_lower for word in [
        "знайдено", "в безпеці", "живий",
        "знаходиться в безпеці", "звільнений з полону", "повернувся з полону",
        "визволений з полону", "обміняли", "обмін полонених", "втік з полону",
    ]):
        return "знайдено і в безпеці"
    elif any(word in text_lower for word in [
        "полон", "в полоні", "список полонених", "попав в полон",
        "потрапив в полон", "взяли в полон", "перебуває в полоні",
        "полонений", "захопили в полон",
    ]):
        return "полон"
    elif any(word in text_lower for word in [
        "загинув", "помер", "померла", "загибель", "убит", "убита", "убитий", "вбитий",
        "загинув під час штурму", "загинув під час обстрілу", "в наслідок атаки дронів",
        "загинув в полоні", "загинув під час бойових дій",
    ]):
        return "загинув"
    elif any(word in text_lower for word in [
        "безвісти", "зникав", "не знайдено", "невідомо де", "невідомих місцеперебування",
        "пропав безвісти", "рахується безвісти зниклим", "список безвісти зниклих",
    ]):
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
        ws = spreadsheet.worksheet("channels missing")
        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            logger.info("📡 Лист 'channels missing' порожній")
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
        logger.error(f"❌ Помилка завантаження channels missing: {type(e).__name__}: {e}", exc_info=True)
        raise


def update_missing_person_found(pib: str, mention_text: str = ""):
    """Оновлює статус особи в Missing Persons таблиці після знаходження публікації."""
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Missing Persons")
        mentions_ws = spreadsheet.worksheet("Mentions")

        all_values = ws.get_all_values()
        mentions_gid = mentions_ws.id

        parts = pib.split()
        search_surname = parts[0].strip() if len(parts) > 0 else ""
        search_name = parts[1].strip() if len(parts) > 1 else ""
        search_patronymic = parts[2].strip() if len(parts) > 2 else ""

        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) >= 4:
                row_surname = row[1].strip() if len(row) > 1 else ""
                row_name = row[2].strip() if len(row) > 2 else ""
                row_patronymic = row[3].strip() if len(row) > 3 else ""

                if (row_surname == search_surname and
                    row_name == search_name and
                    row_patronymic == search_patronymic):

                    updates = {}
                    current_count = 0

                    if len(row) > 7:
                        updates[f"H{idx}"] = "Так"

                    if len(row) > 9:
                        current_count = int(row[9].strip()) if row[9].strip().isdigit() else 0
                        new_count = current_count + 1
                        updates[f"J{idx}"] = str(new_count)

                    if len(row) > 8:
                        new_count = current_count + 1
                        hyperlink = f'=HYPERLINK("https://docs.google.com/spreadsheets/d/{MISSING_PERSONS_SHEET_ID}/edit#gid={mentions_gid}", "Див. Mentions ({new_count} публікацій)")'
                        updates[f"I{idx}"] = hyperlink

                    if len(row) > 10 and mention_text:
                        short_text = mention_text[:300].replace('\n', ' ')
                        updates[f"K{idx}"] = short_text

                    if updates:
                        ws.batch_update(updates)
                        logger.info(f"✅ Оновлено Missing Persons: {pib}")
                    return True

        logger.warning(f"⚠️ Особа {pib} не знайдена в Missing Persons")
        return False
    except Exception as e:
        logger.error(f"❌ Помилка оновлення Missing Persons: {e}")
        return False


def append_to_mentions(mentions: List[Dict]):
    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("Mentions")

        all_rows = ws.get_all_values()
        next_num = len(all_rows)  # header + existing data rows = наступний номер

        for mention in mentions:
            pib = mention.get("pib", "").strip()
            parts = pib.split()
            surname = parts[0] if len(parts) > 0 else ""
            name = parts[1] if len(parts) > 1 else ""
            patronymic = parts[2] if len(parts) > 2 else ""

            text = mention.get("text", "")
            status = detect_status_from_text(text)
            channel_username = mention.get("channel", "")
            channel_url = f"https://t.me/{channel_username}" if channel_username else ""

            row = [
                next_num,
                surname,
                name,
                patronymic,
                status,
                channel_url,
                mention.get("date", ""),
                mention.get("time", ""),
                text,
                mention.get("url", ""),
            ]
            ws.insert_row(row, index=2)
            next_num += 1
            logger.info(f"✅ Запис додано: {pib} в {channel_username} | Статус: {status or 'не визначено'}")

            update_missing_person_found(pib, mention_text=text)

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
