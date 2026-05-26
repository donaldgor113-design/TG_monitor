"""
SQLite база для локального кеша знайдених публікацій.
Потрібна для перевірки дублів перед записом у Google Sheets.
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass


@dataclass
class MentionRecord:
    """Запис про знайдену згадку."""
    person_name: str
    channel_name: str
    message_url: str
    text: str
    found_at: str  # ISO формат
    search_type: str  # "auto" або "manual"
    mention_id: Optional[int] = None


class MissingPersonsDB:
    """
    SQLite база для кешування знайдених згадок.

    Використання:
        db = MissingPersonsDB("mentions.db")

        # Перевірити чи URL вже у базі
        if not db.url_exists("https://t.me/channel/123"):
            # додати в базу
            db.add_mention(...)

        # Отримати все за період
        records = db.get_mentions_by_date("2026-05-20", "2026-05-26")
"""

    def __init__(self, db_path: str = "missing_persons_mentions.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Ініціалізує таблицю якщо її ще немає."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mentions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    person_name TEXT NOT NULL,
                    channel_name TEXT NOT NULL,
                    message_url TEXT UNIQUE NOT NULL,
                    text TEXT,
                    found_at TEXT NOT NULL,
                    search_type TEXT NOT NULL,
                    sheets_synced BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_url ON mentions(message_url)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_person ON mentions(person_name)
            """)
            conn.commit()

    def add_mention(self, record: MentionRecord) -> int:
        """
        Додати новий запис про згадку.

        Args:
            record: MentionRecord об'єкт

        Returns:
            ID записа
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT INTO mentions
                    (person_name, channel_name, message_url, text, found_at, search_type)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    record.person_name,
                    record.channel_name,
                    record.message_url,
                    record.text,
                    record.found_at,
                    record.search_type
                ))
                conn.commit()
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # URL вже існує
                return -1

    def url_exists(self, message_url: str) -> bool:
        """Перевірити чи URL вже у базі."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM mentions WHERE message_url = ?", (message_url,))
            return cursor.fetchone() is not None

    def get_mentions_by_person(self, person_name: str) -> List[MentionRecord]:
        """Отримати всі згадки про конкретну особу."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT person_name, channel_name, message_url, text, found_at, search_type
                FROM mentions
                WHERE person_name = ?
                ORDER BY found_at DESC
            """, (person_name,))

            records = []
            for row in cursor.fetchall():
                records.append(MentionRecord(
                    person_name=row[0],
                    channel_name=row[1],
                    message_url=row[2],
                    text=row[3],
                    found_at=row[4],
                    search_type=row[5]
                ))
            return records

    def get_mentions_by_date(self, date_from: str, date_to: str) -> List[MentionRecord]:
        """Отримати всі згадки за період (ISO формат: YYYY-MM-DD)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT person_name, channel_name, message_url, text, found_at, search_type
                FROM mentions
                WHERE DATE(found_at) BETWEEN ? AND ?
                ORDER BY found_at DESC
            """, (date_from, date_to))

            records = []
            for row in cursor.fetchall():
                records.append(MentionRecord(
                    person_name=row[0],
                    channel_name=row[1],
                    message_url=row[2],
                    text=row[3],
                    found_at=row[4],
                    search_type=row[5]
                ))
            return records

    def get_unsync_mentions(self) -> List[MentionRecord]:
        """Отримати записи які ще не синхронізовані з Google Sheets."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT person_name, channel_name, message_url, text, found_at, search_type
                FROM mentions
                WHERE sheets_synced = 0
                ORDER BY found_at ASC
            """)

            records = []
            for row in cursor.fetchall():
                records.append(MentionRecord(
                    person_name=row[0],
                    channel_name=row[1],
                    message_url=row[2],
                    text=row[3],
                    found_at=row[4],
                    search_type=row[5]
                ))
            return records

    def mark_synced(self, message_url: str) -> bool:
        """Відмітити запис як синхронізований з Google Sheets."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE mentions
                SET sheets_synced = 1
                WHERE message_url = ?
            """, (message_url,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_old_records(self, days: int = 90):
        """Видалити записи старіші ніж N днів."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                DELETE FROM mentions
                WHERE DATE(found_at) < DATE('now', ? || ' days')
            """, (f"-{days}",))
            conn.commit()
            return cursor.rowcount

    def get_stats(self) -> dict:
        """Отримати статистику по БД."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM mentions")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM mentions WHERE sheets_synced = 0")
            unsync = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT person_name) FROM mentions")
            unique_persons = cursor.fetchone()[0]

            return {
                "total_mentions": total,
                "unsynced": unsync,
                "unique_persons": unique_persons
            }


# Приклад використання
if __name__ == "__main__":
    db = MissingPersonsDB()

    # Додати тестовий запис
    record = MentionRecord(
        person_name="Карпенко сергій миколайвич",
        channel_name="agumova_chat",
        message_url="https://t.me/agumova_chat/12345",
        text="Карпенко Сергій виявлений у Харкові...",
        found_at=datetime.now().isoformat(),
        search_type="auto"
    )

    record_id = db.add_mention(record)
    print(f"Запис додано з ID: {record_id}")

    # Перевірити чи URL існує
    exists = db.url_exists("https://t.me/agumova_chat/12345")
    print(f"URL існує: {exists}")

    # Отримати статистику
    stats = db.get_stats()
    print(f"Статистика: {stats}")
