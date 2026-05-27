import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Set

logger = logging.getLogger(__name__)
DB_FILE = "missing_persons.db"


def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pib TEXT NOT NULL,
            channel TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            url TEXT UNIQUE NOT NULL,
            text TEXT,
            post_date TEXT,
            post_time TEXT,
            mention_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def check_url_exists(url: str) -> bool:
    init_db()
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM mentions WHERE url = ?", (url,))
    result = cursor.fetchone()
    conn.close()
    return result is not None


def save_mention(pib: str, channel: str, message_id: int, url: str,
                 text: str = "", post_date: str = "", post_time: str = "",
                 mention_type: str = "missing"):
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO mentions (pib, channel, message_id, url, text, post_date, post_time, mention_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (pib, channel, message_id, url, text, post_date, post_time, mention_type))
        conn.commit()
        conn.close()
        logger.info(f"✅ Згадка збережена: {pib} в {channel}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"⚠️ URL уже існує: {url}")
        return False
    except Exception as e:
        logger.error(f"❌ Помилка збереження: {e}")
        return False


def get_all_urls() -> Set[str]:
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT url FROM mentions")
        urls = {row[0] for row in cursor.fetchall()}
        conn.close()
        return urls
    except Exception as e:
        logger.error(f"❌ Помилка читання URLs: {e}")
        return set()


def get_mentions_count() -> int:
    init_db()
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM mentions")
        count = cursor.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        logger.error(f"❌ Помилка підрахунку: {e}")
        return 0
