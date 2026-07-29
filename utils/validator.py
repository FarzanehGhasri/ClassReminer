import re

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_PATTERN.match(email.strip()))


def is_valid_chat_id(chat_id: str) -> bool:
    return bool(chat_id and chat_id.strip())


def validate_recipient_row(row: dict) -> list:
    problems = []
    if not row.get("name", "").strip():
        problems.append("missing name")

    email = row.get("email", "").strip()
    telegram_id = row.get("telegram_chat_id", "").strip()
    bale_id = row.get("bale_chat_id", "").strip()
    if not (email or telegram_id or bale_id):
        problems.append("no contact method provided")
    if email and not is_valid_email(email):
        problems.append(f"invalid email format: {email}")

    if not row.get("schedule_weekday", "").strip():
        problems.append("missing schedule_weekday")
    if not row.get("schedule_time", "").strip():
        problems.append("missing schedule_time")

    return problems