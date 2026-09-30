"""
The Student entity and the rules it refuses to be built without.

Invariants live on the entity, so no caller can construct a Student that the
database would reject. The web form, the CSV importer and any future admin
screen all go through Student.create and get the same answer.
"""
from dataclasses import dataclass
from typing import Dict, Optional

from core.models.country import Country
from core.models.phone_number import InvalidPhoneNumber, PhoneNumber
from utils.validator import is_valid_email, is_valid_persian_name

MAX_NAME_LENGTH = 60
MAX_EMAIL_LENGTH = 254


class StudentValidationError(ValueError):
    """Carries one Persian message per bad field, keyed by form field name."""

    def __init__(self, errors: Dict[str, str]):
        self.errors = errors
        super().__init__("; ".join(f"{field}: {msg}" for field, msg in errors.items()))


@dataclass(frozen=True)
class Student:
    first_name: str
    last_name: str
    phone: PhoneNumber
    email: str

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @staticmethod
    def create(
        first_name: str,
        last_name: str,
        phone_raw: str,
        email: str,
        country: Optional[Country],
    ) -> "Student":
        """Validate every field and report all problems at once, so the form
        can mark each bad input instead of revealing them one refresh apart."""
        errors: Dict[str, str] = {}

        first_name = (first_name or "").strip()
        last_name = (last_name or "").strip()
        email = (email or "").strip()

        if not first_name:
            errors["first_name"] = "نام را وارد کنید."
        elif len(first_name) > MAX_NAME_LENGTH:
            errors["first_name"] = f"نام نباید بیش از {MAX_NAME_LENGTH} نویسه باشد."
        elif not is_valid_persian_name(first_name):
            errors["first_name"] = "نام باید فقط با حروف فارسی نوشته شود."

        if not last_name:
            errors["last_name"] = "نام خانوادگی را وارد کنید."
        elif len(last_name) > MAX_NAME_LENGTH:
            errors["last_name"] = f"نام خانوادگی نباید بیش از {MAX_NAME_LENGTH} نویسه باشد."
        elif not is_valid_persian_name(last_name):
            errors["last_name"] = "نام خانوادگی باید فقط با حروف فارسی نوشته شود."

        phone: Optional[PhoneNumber] = None
        if country is None:
            errors["country"] = "کشور را انتخاب کنید."
        else:
            try:
                phone = PhoneNumber.parse(phone_raw, country)
            except InvalidPhoneNumber as error:
                errors["phone"] = str(error)

        if not email:
            errors["email"] = "ایمیل را وارد کنید."
        elif len(email) > MAX_EMAIL_LENGTH:
            errors["email"] = "ایمیل بیش از حد طولانی است."
        elif not is_valid_email(email):
            errors["email"] = "فرمت ایمیل صحیح نیست."

        if errors:
            raise StudentValidationError(errors)

        return Student(
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            email=email,
        )
