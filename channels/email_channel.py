from datetime import date

from core.interfaces import NotificationChannel, TemplateRenderer
from core.models import Recipient
from infrastructure.smtp_client import SmtpClient
from utils.retry import retry_on_failure
from utils.validator import is_valid_email


class EmailChannel(NotificationChannel):
    def __init__(self, smtp_client: SmtpClient, renderer: TemplateRenderer):
        self._smtp_client = smtp_client
        self._renderer = renderer

    @property
    def channel_name(self) -> str:
        return "email"

    def can_send_to(self, recipient: Recipient) -> bool:
        return is_valid_email(recipient.email)

    @retry_on_failure(max_attempts=3, delay_seconds=5)
    def send(self, recipient: Recipient, link: str) -> None:
        fields = {
            "name": recipient.name,
            "class_link": link,
            "date": date.today(),
            "schedule_time": recipient.schedule.send_time.strftime("%H:%M"),
            "schedule_weekday": recipient.schedule.weekday_name,
        }
        subject = self._renderer.render("subject.txt", **fields)
        body = self._renderer.render("body.txt", **fields)
        self._smtp_client.send(recipient.email, subject, body)