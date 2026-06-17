import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from config import MISSING_PERSONS_SHEET_ID
from typing import List, Dict, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from missing_persons.utils import PersonData

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


def load_missing_persons() -> Dict[str, 'PersonData']:
    from missing_persons.utils import PersonData

    try:
        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("missing persons")
        all_values = ws.get_all_values()

        if len(all_values) <= 1:
            logger.info("📋 Лист 'Missing Persons' порожній")
            return {}

        persons = {}
        for row in all_values[1:]:
            if len(row) >= 8:
                # Індекси після додання колонок:
                # 0: ID, 1: Прізвище, 2: Ім'я, 3: По-батькові,
                # 4: Дата народження, 5: Додано, 6: Розшукується з:, 7: Статус
                surname = row[1].strip() if len(row) > 1 else ""
                name = row[2].strip() if len(row) > 2 else ""
                patronymic = row[3].strip() if len(row) > 3 else ""
                birth_date = row[4].strip() if len(row) > 4 else ""
                missing_from_date = row[6].strip() if len(row) > 6 else ""
                status = row[7].strip().lower() if len(row) > 7 else ""

                if surname and name and status == "missing":
                    full_name = f"{surname} {name}".strip()
                    if patronymic:
                        full_name = f"{full_name} {patronymic}"

                    persons[full_name] = PersonData(
                        surname=surname,
                        name=name,
                        patronymic=patronymic,
                        birth_date=birth_date,
                        missing_from_date=missing_from_date,
                        status=status
                    )
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
        from gspread.utils import rowcol_to_a1
        from gspread.utils import a1_range_to_grid_range

        spreadsheet = get_spreadsheet()
        ws = spreadsheet.worksheet("missing persons")
        mentions_ws = spreadsheet.worksheet("Mentions")

        all_values = ws.get_all_values()
        mentions_gid = mentions_ws.id

        parts = pib.split()
        search_surname = parts[0].strip() if len(parts) > 0 else ""
        search_name = parts[1].strip() if len(parts) > 1 else ""
        search_patronymic = parts[2].strip() if len(parts) > 2 else ""

        for idx, row in enumerate(all_values[1:], start=2):
            if len(row) >= 4:
                # Індекси: 1: Прізвище, 2: Ім'я, 3: По-батькові
                row_surname = row[1].strip() if len(row) > 1 else ""
                row_name = row[2].strip() if len(row) > 2 else ""
                row_patronymic = row[3].strip() if len(row) > 3 else ""

                if (row_surname == search_surname and
                    row_name == search_name and
                    row_patronymic == search_patronymic):

                    updates = {}
                    current_count = 0

                    # Встановлюємо "Знайдено" в колонці J (раніше H)
                    if len(row) > 9:
                        updates[f"J{idx}"] = "Знайдено"

                    # Обновляємо кількість публікацій в колонці L (раніше J)
                    if len(row) > 11:
                        current_count = int(row[11].strip()) if row[11].strip().isdigit() else 0
                        new_count = current_count + 1
                        updates[f"L{idx}"] = str(new_count)

                    # Обновляємо посилання на публікації в колонці K (раніше I)
                    if len(row) > 10:
                        new_count = current_count + 1
                        hyperlink = f'=HYPERLINK("https://docs.google.com/spreadsheets/d/{MISSING_PERSONS_SHEET_ID}/edit#gid={mentions_gid}", "Див. Mentions ({new_count} публікацій)")'
                        updates[f"K{idx}"] = hyperlink

                    # Обновляємо текст публікації в колонці M (раніше K)
                    if len(row) > 12 and mention_text:
                        short_text = mention_text[:300].replace('\n', ' ')
                        updates[f"M{idx}"] = short_text

                    if updates:
                        try:
                            update_data = [{"range": cell_ref, "values": [[val]]} for cell_ref, val in updates.items()]
                            ws.batch_update(update_data)
                        except Exception as e:
                            logger.warning(f"⚠️ Помилка оновлення колонок {pib}: {e}")

                    # Фарбуємо рядок в світлий зелений колір
                    try:
                        requests = [{
                            "repeatCell": {
                                "range": {
                                    "sheetId": ws.id,
                                    "startRowIndex": idx - 1,
                                    "endRowIndex": idx,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "backgroundColor": {
                                            "red": 0.8,
                                            "green": 1.0,
                                            "blue": 0.8,
                                            "alpha": 1.0
                                        }
                                    }
                                },
                                "fields": "userEnteredFormat.backgroundColor"
                            }
                        }]
                        spreadsheet.batch_update({"requests": requests})
                        logger.info(f"✅ Оновлено Missing Persons: {pib} (фарбування + статус)")
                    except Exception as e:
                        logger.warning(f"⚠️ Помилка фарбування рядка {idx}: {e}")
                        logger.info(f"✅ Оновлено Missing Persons: {pib} (але без фарбування)")

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

            from datetime import datetime
            recorded_at = datetime.now().strftime("%d.%m.%Y %H:%M")

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
                recorded_at,
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
