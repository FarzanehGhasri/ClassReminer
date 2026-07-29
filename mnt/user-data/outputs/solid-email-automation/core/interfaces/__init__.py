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
