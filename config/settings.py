import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "smtp")  # "smtp" or "brevo"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USERNAME = os.environ.get("SMTP_USERNAME", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "")

TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

BALE_API_BASE = "https://tapi.bale.ai"
BALE_BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN", "")

RECIPIENTS_CSV_PATH = os.environ.get("RECIPIENTS_CSV_PATH", os.path.join(BASE_DIR, "data", "students.csv"))
SENT_LOG_DB_PATH = os.environ.get("SENT_LOG_DB_PATH", os.path.join(BASE_DIR, "data", "sent_log.db"))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

SCHEDULE_TOLERANCE_MINUTES = int(os.environ.get("SCHEDULE_TOLERANCE_MINUTES", "5"))
NOTIFICATION_LEAD_MINUTES = int(os.environ.get("NOTIFICATION_LEAD_MINUTES", "30"))
DEFAULT_CLASS_LINK = "https://meet.google.com/your-default-link"
ADMIN_ALERT_EMAIL = os.environ.get("ADMIN_ALERT_EMAIL", "")