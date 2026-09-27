import re

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Kept deliberately in step with the domains in db/init/01_schema.sql.
# The database is the authority — these let the app reject bad input early
# (and give a Persian error message) instead of waiting for an IntegrityError.

# Persian letters: the Arabic block ranges plus the Persian-specific
# پ (067E) چ (0686) ژ (0698) ک (06A9) گ (06AF) ی (06CC).
_PERSIAN_LETTER = r"ء-غف-يپچژھکگی"
# Words may be joined by a space, a hyphen, or ZWNJ (U+200C, the نیم‌فاصله).
PERSIAN_NAME_PATTERN = re.compile(
    rf"^[{_PERSIAN_LETTER}]+([ ‌\-][{_PERSIAN_LETTER}]+)*$"
)

# Iranian mobile: starts with 09, exactly 11 digits.
IRAN_MOBILE_PATTERN = re.compile(r"^09\d{9}$")

# Persian/Arabic-Indic digits, so a number typed on a Persian keyboard
# can be normalised rather than rejected.
_DIGIT_TRANSLATION = str.maketrans(
    "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
    "01234567890123456789",
)


def is_valid_email(email: str) -> bool:
    return bool(email) and bool(EMAIL_PATTERN.match(email.strip()))


def is_valid_chat_id(chat_id: str) -> bool:
    return bool(chat_id and chat_id.strip())


def is_valid_persian_name(name: str) -> bool:
    """True only for a name written in Persian letters. Latin text, digits
    and mixed script are rejected, matching the persian_name SQL domain."""
    return bool(name) and bool(PERSIAN_NAME_PATTERN.match(name.strip()))


def normalize_phone_number(phone: str) -> str:
    """Bring the common ways of writing an Iranian mobile into the single
    form the database stores: 09XXXXXXXXX.

    Handles Persian digits, spaces and dashes, a +98/0098/98 country code,
    and the 9XXXXXXXXX form with the leading zero left off.
    """
    if not phone:
        return ""

    digits = phone.strip().translate(_DIGIT_TRANSLATION)
    digits = re.sub(r"[\s\-()]", "", digits)

    if digits.startswith("+"):
        digits = digits[1:]
    if digits.startswith("0098"):
        digits = digits[4:]
    elif digits.startswith("98") and len(digits) == 12:
        digits = digits[2:]

    # 9XXXXXXXXX — a leading zero was dropped, as often happens in spreadsheets.
    if len(digits) == 10 and digits.startswith("9"):
        digits = "0" + digits

    return digits


def is_valid_iran_mobile(phone: str) -> bool:
    """True for an Iranian mobile number, after normalisation."""
    return bool(IRAN_MOBILE_PATTERN.match(normalize_phone_number(phone)))


def validate_student(first_name: str, last_name: str, phone: str, email: str) -> list:
    """Row-level check used when importing or registering a student.
    Returns a list of human-readable problems; empty means the row is good."""
    problems = []

    if not is_valid_persian_name(first_name):
        problems.append(f"first_name must be written in Persian: {first_name!r}")
    if not is_valid_persian_name(last_name):
        problems.append(f"last_name must be written in Persian: {last_name!r}")
    if not is_valid_iran_mobile(phone):
        problems.append(f"phone_number must be an Iranian mobile (09XXXXXXXXX): {phone!r}")
    if not is_valid_email(email):
        problems.append(f"invalid email format: {email!r}")

    return problems


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
