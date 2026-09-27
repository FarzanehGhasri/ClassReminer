"""
Concrete implementation of core.interfaces.RecipientRepository backed by
PostgreSQL — the swap the README always promised. core/scheduler.py is
untouched by this file existing.

One row per enrolment: a student in three classes yields three Recipients,
which is what lets a single scheduler run remind them about each one.
"""
import logging
from typing import List

import psycopg
from psycopg.rows import dict_row

from core.interfaces import RecipientRepository
from core.models import WEEKDAY_NAME_TO_INDEX, Recipient, Schedule

logger = logging.getLogger(__name__)

# The join lives in the enrolment_reminder view (db/init/01_schema.sql), so
# the shape the scheduler needs is defined in one place, in SQL.
_LOAD_QUERY = """
    SELECT full_name,
           email,
           telegram_chat_id,
           bale_chat_id,
           class_id,
           class_day::text AS class_day,
           class_time,
           class_link
    FROM enrolment_reminder
    ORDER BY class_day, class_time, student_id
"""


class PostgresStudentRepository(RecipientRepository):
    """Reads student/class/student_class over a short-lived connection.

    The scheduler runs as a one-shot job every few minutes (cron or the
    systemd timer in deploy/), so connecting per run and closing again
    avoids holding a connection idle — and avoids using a stale one.
    """

    def __init__(self, dsn: str, connect_timeout: int = 10):
        self._dsn = dsn
        self._connect_timeout = connect_timeout

    def load_all(self) -> List[Recipient]:
        with psycopg.connect(
            self._dsn, connect_timeout=self._connect_timeout, row_factory=dict_row
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(_LOAD_QUERY)
                rows = cur.fetchall()

        recipients = [self._row_to_recipient(row) for row in rows]
        logger.info("Loaded %d enrolment(s) from PostgreSQL", len(recipients))
        return recipients

    @staticmethod
    def _row_to_recipient(row: dict) -> Recipient:
        # class_day is a weekday enum whose labels match WEEKDAY_NAME_TO_INDEX,
        # and class_time comes back as a datetime.time.
        schedule = Schedule(
            weekday=WEEKDAY_NAME_TO_INDEX[row["class_day"]],
            send_time=row["class_time"],
        )
        return Recipient(
            name=row["full_name"],
            email=row["email"] or "",
            telegram_chat_id=row["telegram_chat_id"] or "",
            bale_chat_id=row["bale_chat_id"] or "",
            message_link=row["class_link"] or "",
            schedule=schedule,
            class_id=row["class_id"],
        )
