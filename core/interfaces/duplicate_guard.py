from abc import ABC, abstractmethod


class DuplicateGuard(ABC):
    """Prevents sending the same recipient the same channel twice in one
    period. SQLite today; could be Redis or a database table tomorrow."""

    @abstractmethod
    def already_sent(self, recipient_key: str, channel: str) -> bool:
        ...

    @abstractmethod
    def mark_sent(self, recipient_key: str, channel: str) -> None:
        ...