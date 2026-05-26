# config.py
import os
import json
import logging
from dotenv import load_dotenv


load_dotenv()


# ── Токени та ID ────────────────────────────────────────
BOT_TOKEN      = os.getenv("BOT_TOKEN")
API_ID         = int(os.getenv("API_ID"))
API_HASH       = os.getenv("API_HASH")
ADMIN_ID       = int(os.getenv("ADMIN_CHAT_ID"))
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
ALERT_CHANNEL  = os.getenv("ALERT_CHANNEL", None)
DEFAULT_SHARED_ADMIN_ID = 7004336488


# ── Константи ───────────────────────────────────────────
DATA_FILE    = "monitor_data.json"
MIN_HITS_OLD = 1
MIN_HITS_NEW = 1


# ── Логер ───────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



# ── Робота з JSON-даними ────────────────────────────────
def load_data() -> dict:
    default_admin_ids = sorted({ADMIN_ID, DEFAULT_SHARED_ADMIN_ID})
    defaults = {
        "channels": [],
        "keywords": [],
        "live_active_channels": [],
        "live_active_keywords": [],
        "arc_active_channels": [],
        "arc_active_keywords": [],
        "date_from": None,
        "date_to": None,
        "monitoring": False,
        "classifier_mode": "legacy",
        "admin_ids": default_admin_ids,
        "owner_ids": default_admin_ids,
        "archive_running": False,
        "active_session_user": None,
    }
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        for key, value in defaults.items():
            data.setdefault(key, value)
        return data
    return defaults



def save_data(data: dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)



def _normalize_id_list(values) -> list[int]:
    result = []
    for value in values or []:
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            continue
        if user_id not in result:
            result.append(user_id)
    return result



def get_admin_ids(data: dict | None = None) -> list[int]:
    source = data if data is not None else load_data()
    admins = _normalize_id_list(source.get("admin_ids", []))
    if not admins:
        admins = sorted({ADMIN_ID, DEFAULT_SHARED_ADMIN_ID})
    return admins



def get_owner_ids(data: dict | None = None) -> list[int]:
    source = data if data is not None else load_data()
    owners = _normalize_id_list(source.get("owner_ids", []))
    if not owners:
        owners = get_admin_ids(source)
    return owners



def is_admin(user_id: int, data: dict | None = None) -> bool:
    return int(user_id) in get_admin_ids(data)



def is_owner(user_id: int, data: dict | None = None) -> bool:
    return int(user_id) in get_owner_ids(data)



async def notify_admins(bot, text: str, **kwargs):
    for admin_id in get_admin_ids():
        try:
            await bot.send_message(admin_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Не вдалося надіслати повідомлення адміну {admin_id}: {e}")



async def notify_owners(bot, text: str, **kwargs):
    for owner_id in get_owner_ids():
        try:
            await bot.send_message(owner_id, text, **kwargs)
        except Exception as e:
            logger.error(f"Не вдалося надіслати повідомлення власнику {owner_id}: {e}")



def get_active_session(d: dict) -> dict | None:
    if d.get("monitoring"):
        return {
            "type": "live",
            "user_id": d.get("active_session_user"),
            "channels": len(d.get("live_active_channels", [])),
            "keywords": len(d.get("live_active_keywords", [])),
        }
    if d.get("archive_running"):
        return {
            "type": "archive",
            "user_id": d.get("active_session_user"),
            "channels": len(d.get("arc_active_channels", [])),
            "keywords": len(d.get("arc_active_keywords", [])),
        }
    return None



# ── Утиліта ─────────────────────────────────────────────
def escape_html(text: str) -> str:
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")