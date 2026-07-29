"""
Composition root. This is the ONE place in the codebase allowed to import
concrete classes from infrastructure/ and channels/ directly — everywhere
else works through core/interfaces.py.

To reuse this whole framework in a future project: keep core/ and utils/
as-is, write new infrastructure/ and channels/ implementations for
whatever's different (a new data source, a new send channel), and wire
them here.
"""
from config import settings
from core.scheduler import ScheduleChecker, Scheduler
from channels.bale_channel import BaleChannel
from channels.email_channel import EmailChannel
from channels.telegram_channel import TelegramChannel
from infrastructure.bot_api_client import BotApiClient
#from infrastructure.brevo_email_client import BrevoEmailClient
from infrastructure.csv_recipient_repository import CsvRecipientRepository
from infrastructure.email_admin_alerter import EmailAdminAlerter
from infrastructure.file_template_renderer import FileTemplateRenderer
from infrastructure.smtp_client import SmtpClient, SmtpCredentials
from infrastructure.sqlite_duplicate_guard import SqliteDuplicateGuard
from utils.logger import setup_logging


def build_email_client():
    """Picks the email transport based on EMAIL_PROVIDER in .env.
    'smtp' = raw SMTP (needs port 465/587 open).
    'brevo' = HTTPS API (works when SMTP ports are blocked)."""
    #if settings.EMAIL_PROVIDER == "brevo":
    #    return BrevoEmailClient(
    #        api_key=settings.BREVO_API_KEY,
    #        sender_email=settings.BREVO_SENDER_EMAIL,
    #    )
    return SmtpClient(SmtpCredentials(
        host=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
    ))


def build_scheduler() -> Scheduler:
    email_client = build_email_client()
    renderer = FileTemplateRenderer(settings.TEMPLATES_DIR)

    channels = [
        EmailChannel(email_client, renderer),
        TelegramChannel(BotApiClient(settings.TELEGRAM_API_BASE, settings.TELEGRAM_BOT_TOKEN)),
        BaleChannel(BotApiClient(settings.BALE_API_BASE, settings.BALE_BOT_TOKEN)),
    ]

    return Scheduler(
        repository=CsvRecipientRepository(settings.RECIPIENTS_CSV_PATH),
        schedule_checker=ScheduleChecker(settings.SCHEDULE_TOLERANCE_MINUTES, settings.NOTIFICATION_LEAD_MINUTES),
        duplicate_guard=SqliteDuplicateGuard(settings.SENT_LOG_DB_PATH),
        channels=channels,
        default_link=settings.DEFAULT_CLASS_LINK,
        failure_handler=EmailAdminAlerter(email_client, settings.ADMIN_ALERT_EMAIL),
    )


if __name__ == "__main__":
    setup_logging()
    build_scheduler().run()