from abc import ABC, abstractmethod

from core.models import Recipient


class NotificationChannel(ABC):
    """One delivery mechanism: email, Telegram, Bale, WhatsApp, SMS...
    Add a new channel by implementing this — no existing code changes
    (Open/Closed)."""

    @property
    @abstractmethod
    def channel_name(self) -> str:
        ...

    @abstractmethod
    def can_send_to(self, recipient: Recipient) -> bool:
        """Whether this recipient has the contact info this channel needs."""

    @abstractmethod
    def send(self, recipient: Recipient, link: str) -> None:
        """Send the notification. Raise on failure — callers handle it."""