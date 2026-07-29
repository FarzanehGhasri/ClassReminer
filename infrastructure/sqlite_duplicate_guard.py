"""
Concrete implementation of core.interfaces.DuplicateGuard.
Swap for a Redis- or database-backed guard in a future project without
touching core/scheduler.py.
"""
import sqlite3
from datetime import date

from core.interfaces import DuplicateGuard


class SqliteDuplicateGuard(DuplicateGuard):
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """CREATE TABLE IF NOT EXISTS sent_log (
                   recipient_key TEXT NOT NULL,
                   channel TEXT NOT NULL,
                   date_sent TEXT NOT NULL,
                   PRIMARY KEY (recipient_key, channel, date_sent)
               )"""
        )
        self._conn.commit()

    def already_sent(self, recipient_key: str, channel: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM sent_log WHERE recipient_key = ? AND channel = ? AND date_sent = ?",
            (recipient_key, channel, str(date.today())),
        ).fetchone()
        return row is not None

    def mark_sent(self, recipient_key: str, channel: str) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO sent_log (recipient_key, channel, date_sent) VALUES (?, ?, ?)",
            (recipient_key, channel, str(date.today())),
        )
        self._conn.commit()