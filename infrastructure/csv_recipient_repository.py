"""
Concrete implementation of core.interfaces.RecipientRepository.
Swap this for GoogleSheetRecipientRepository or DatabaseRecipientRepository
in a future project — core/scheduler.py wouldn't need to change at all.
"""
import csv
import logging
from typing import List

from core.interfaces import RecipientRepository
from core.models import Recipient, Schedule
from utils.validator import validate_recipient_row

logger = logging.getLogger(__name__)


class CsvRecipientRepository(RecipientRepository):
    def __init__(self, csv_path: str):
        self._csv_path = csv_path

    def load_all(self) -> List[Recipient]:
        recipients = []
        with open(self._csv_path, newline="", encoding="utf-8") as f:
            for row_number, row in enumerate(csv.DictReader(f), start=2):
                problems = validate_recipient_row(row)
                if problems:
                    logger.warning("Skipping row %d (%s): %s", row_number, row.get("name", "?"), "; ".join(problems))
                    continue
                recipients.append(self._row_to_recipient(row))
        return recipients

    @staticmethod
    def _row_to_recipient(row: dict) -> Recipient:
        schedule = Schedule.from_strings(row["schedule_weekday"], row["schedule_time"])
        return Recipient(
            name=row["name"].strip(),
            email=row.get("email", "").strip(),
            telegram_chat_id=row.get("telegram_chat_id", "").strip(),
            bale_chat_id=row.get("bale_chat_id", "").strip(),
            message_link=row.get("message_link", "").strip(),
            schedule=schedule,
        )