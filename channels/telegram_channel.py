from core.interfaces import NotificationChannel
from core.models import Recipient
from infrastructure.bot_api_client import BotApiClient
from utils.retry import retry_on_failure
from utils.validator import is_valid_chat_id


class TelegramChannel(NotificationChannel):
    def __init__(self, client: BotApiClient):
        self._client = client

    @property
    def channel_name(self) -> str:
        return "telegram"

    def can_send_to(self, recipient: Recipient) -> bool:
        return is_valid_chat_id(recipient.telegram_chat_id)

    @retry_on_failure(max_attempts=3, delay_seconds=5)
    def send(self, recipient: Recipient, link: str) -> None:
        text = f"Hi {recipient.name}, here is your class link:\n{link}"
        self._client.send_message(recipient.telegram_chat_id, text)