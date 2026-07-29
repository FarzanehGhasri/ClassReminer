from abc import ABC, abstractmethod
from typing import List

from core.models import Recipient


class RecipientRepository(ABC):
    """Wherever recipient data lives — CSV today, a database or Google
    Sheet tomorrow. Swappable without touching the scheduler (Liskov:
    any implementation is interchangeable wherever this type is used)."""

    @abstractmethod
    def load_all(self) -> List[Recipient]:
        ...