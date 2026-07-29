from abc import ABC, abstractmethod

from core.models import Recipient


class FailureHandler(ABC):
    """What to do when a send fails — email an admin, post to Slack, etc."""

    @abstractmethod
    def handle(self, recipient: "Recipient | None", channel: str, error: Exception) -> None:
        ...