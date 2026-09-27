from dataclasses import dataclass
from typing import Optional

from core.models.schedule import Schedule


@dataclass(frozen=True)
class Recipient:
    name: str
    email: str
    telegram_chat_id: str
    bale_chat_id: str
    message_link: str
    schedule: Schedule
    # Which class this reminder is for. None for sources that have no notion
    # of a class (the CSV repository), set by the Postgres repository.
    class_id: Optional[int] = None

    @property
    def unique_key(self) -> str:
        """Identifies one reminder for the duplicate guard.

        The class is part of the key on purpose: a student enrolled in two
        classes on the same day must get both reminders, and keying on the
        contact alone would suppress the second."""
        contact = self.email or self.telegram_chat_id or self.bale_chat_id or self.name
        if self.class_id is None:
            return contact
        return f"{contact}#class{self.class_id}"
