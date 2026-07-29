"""
Deliberately empty. `core` is never imported as a whole (no
`from core import X`) — always via its submodules:
`core.models`, `core.interfaces`, `core.scheduler`. Adding re-exports
here would also risk a circular import, since core.scheduler imports
from core.interfaces and core.models.
"""

from core.interfaces.duplicate_guard import DuplicateGuard
from core.interfaces.failure_handler import FailureHandler
from core.interfaces.notification_channel import NotificationChannel
from core.interfaces.recipient_repository import RecipientRepository
from core.interfaces.template_renderer import TemplateRenderer

__all__ = [
    "NotificationChannel",
    "RecipientRepository",
    "DuplicateGuard",
    "TemplateRenderer",
    "FailureHandler",
]