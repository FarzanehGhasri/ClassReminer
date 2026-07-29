from dataclasses import dataclass

from core.models.schedule import Schedule


@dataclass(frozen=True)
class Recipient:
    name: str
    email: str
    telegram_chat_id: str
    bale_chat_id: str
    message_link: str
    schedule: Schedule

    @property
    def unique_key(self) -> str:
        return self.email or self.telegram_chat_id or self.bale_chat_id or self.name