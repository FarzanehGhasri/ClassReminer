import re

# Mirrors the email_address domain in db/init/01_schema.sql character for
# character. A looser pattern here would let the form accept an address the
# database then rejects, turning a fixable field error into a server error.
EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+"
    r"@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$"
)
MAX_EMAIL_LENGTH = 254

# Kept deliberately in step with the domains in db/init/01_schema.sql.
# The database is the authority — these let the app reject bad input early
# (and give a Persian error message) instead of waiting for an IntegrityError.
#
# Phone numbers are NOT handled here: validating one needs the country the
# student picked, so that logic lives in core/models/phone_number.py together
# with the country registry it depends on.

# Persian letters: the Arabic block ranges plus the Persian-specific
# پ (067E) چ (0686) ژ (0698) ک (06A9) گ (06AF) ی (06CC).
_PERSIAN_LETTER = "ء-غف-يپچژھکگی"
# Words may be joined by a space, a hyphen, or ZWNJ (U+200C, the نیم‌فاصله).
PERSIAN_NAME_PATTERN = re.compile(
    rf"^[{_PERSIAN_LETTER}]+([ ‌\-][{_PERSIAN_LETTER}]+)*$"
)


def is_valid_email(email: str) -> bool:
    email = (email or "").strip()
    if not email or len(email) > MAX_EMAIL_LENGTH or ".." in email:
        return False
    return bool(EMAIL_PATTERN.match(email))


def is_valid_chat_id(chat_id: str) -> bool:
    return bool(chat_id and chat_id.strip())


def is_valid_persian_name(name: str) -> bool:
    """True only for a name written in Persian letters. Latin text, digits
    and mixed script are rejected, matching the persian_name SQL domain."""
    return bool(name) and bool(PERSIAN_NAME_PATTERN.match(name.strip()))


def validate_recipient_row(row: dict) -> list:
    """Row check for the legacy CSV recipient source (RECIPIENT_SOURCE=csv)."""
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
