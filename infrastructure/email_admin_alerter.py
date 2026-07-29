import logging

from core.interfaces import FailureHandler
from infrastructure.smtp_client import SmtpClient

logger = logging.getLogger(__name__)


class EmailAdminAlerter(FailureHandler):
    """Best-effort alert to the operator. A failure here is swallowed on
    purpose — an alerting bug must never crash the main run."""

    def __init__(self, smtp_client: SmtpClient, admin_email: str):
        self._smtp_client = smtp_client
        self._admin_email = admin_email

    def handle(self, recipient, channel: str, error: Exception) -> None:
        if not self._admin_email:
            return
        who = recipient.name if recipient else "N/A"
        body = f"Notifier failure.\nRecipient: {who}\nChannel: {channel}\nError: {error}"
        try:
            self._smtp_client.send(self._admin_email, "Class Notifier — send failure", body)
        except Exception as alert_error:
            logger.error("Failed to send admin alert itself: %s", alert_error)