# sheets.py
import logging
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from keywords import KEYWORD_TO_SHEET

logger = logging.getLogger(__name__)

SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
SHEET_COLUMNS  = ["№п/п", "channel", "date", "time", "url", "post", "keyword1", "keywords", "comments"]


def get_spreadsheet():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds  = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID)


def ensure_header(worksheet):
    try:
        first_row = worksheet.row_values(1)
        if not first_row:
            worksheet.append_row(SHEET_COLUMNS)
    except Exception as e:
        logger.error(f"Помилка заголовку: {e}")


def load_all_existing_urls(spreadsheet) -> dict:
    existing    = {}
    sheet_names = set(KEYWORD_TO_SHEET.values())
    for name in sheet_names:
        try:
            ws         = spreadsheet.worksheet(name)
            ensure_header(ws)
            all_values = ws.get_all_values()
            logger.info(f"📊 Вкладка '{name}': всього рядків = {len(all_values)}")
            if len(all_values) <= 1:
                existing[name] = set()
                logger.info(f"✅ '{name}': пуста (немає даних)")
            else:
                urls = {
                    row[4] for row in all_values[1:]
                    if len(row) > 4 and row[4]
                }
                existing[name] = urls
                logger.info(f"✅ '{name}': завантажено {len(urls)} URLs: {list(urls)[:3]}")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning(f"Вкладка '{name}' не знайдена в таблиці!")
            existing[name] = set()
        except Exception as e:
            logger.error(f"Помилка читання вкладки '{name}': {e}")
            existing[name] = set()
    return existing


def append_to_sheet(
    spreadsheet,
    matched_keyword: str,
    channel: str,
    date_str: str,
    time_str: str,
    url: str,
    text: str,
    keyword1: str = "",
    keywords: str = "",
) -> bool:
    logger.info(f"🔍 append_to_sheet: matched_keyword='{matched_keyword}'")
    sheet_name = KEYWORD_TO_SHEET.get(matched_keyword)
    logger.info(f"📋 KEYWORD_TO_SHEET.get('{matched_keyword}') = '{sheet_name}'")
    if not sheet_name:
        logger.error(f"❌ Немає вкладки для ключового слова: '{matched_keyword}'")
        logger.info(f"📚 Доступні ключові слова: {list(KEYWORD_TO_SHEET.keys())}")
        return False

    if url == "—":
        logger.warning(f"⚠️ URL є '—', пропускаю")
        return False

    try:
        logger.info(f"📄 Отримую worksheet '{sheet_name}'")
        ws         = spreadsheet.worksheet(sheet_name)
        all_values = ws.get_all_values()

        logger.info(f"📊 all_values length: {len(all_values)}")

        # ── Порядковий номер — береться з кількості існуючих записів ──
        next_num = len(all_values)

        row_data = [next_num, channel, date_str, time_str, url, text, keyword1, keywords, ""]
        logger.info(f"➕ Вставляю рядок: {row_data}")

        # ── Вставляємо рядок ПІСЛЯ заголовка (рядок 2) ──────────────
        ws.insert_row(row_data, index=2)
        logger.info(f"✅ Рядок вставлено успішно!")
        return True

    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"❌ Вкладка '{sheet_name}' не знайдена!")
        return False
    except Exception as e:
        logger.error(f"❌ Помилка при insert_row: {e}", exc_info=True)
        return False
