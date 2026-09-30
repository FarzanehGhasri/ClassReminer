"""
A phone number the database will accept, and the parsing that gets it there.

Students type numbers the way their country writes them — 0912…, +98 912…,
۰۹۱۲… on a Persian keyboard, with spaces and dashes. All of those mean the
same number. This turns any of them into one canonical E.164 string, or
refuses them with a reason.
"""
import re
from dataclasses import dataclass

from core.models.country import Country

# Persian and Arabic-Indic digits, so a number typed on a Persian keyboard
# is understood rather than rejected.
_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


class InvalidPhoneNumber(ValueError):
    """Raised with a Persian message the form can show as-is."""


@dataclass(frozen=True)
class PhoneNumber:
    e164: str          # "+989122025452" — exactly what the student column stores
    country: Country

    @property
    def national(self) -> str:
        return self.e164[len(self.country.dial_code):]

    @property
    def local_format(self) -> str:
        """How the owner would write it: 09122025452 for Iran."""
        return f"{self.country.trunk_prefix}{self.national}"

    def __str__(self) -> str:
        return self.e164

    @staticmethod
    def parse(raw: str, country: Country) -> "PhoneNumber":
        if raw is None or not raw.strip():
            raise InvalidPhoneNumber("شماره تماس را وارد کنید.")

        digits = _to_digits(raw)
        if not digits:
            raise InvalidPhoneNumber("شماره تماس فقط باید شامل رقم باشد.")

        national = _find_national_number(digits, country)
        if national is None:
            raise InvalidPhoneNumber(
                f"شماره برای {country.name_fa} معتبر نیست — {country.hint_fa}."
            )

        return PhoneNumber(e164=f"{country.dial_code}{national}", country=country)


def _to_digits(raw: str) -> str:
    """Normalise digits and drop the punctuation people type: spaces, dashes,
    brackets. A leading 00 is the other way of writing +."""
    text = raw.strip().translate(_DIGIT_TRANSLATION)
    text = re.sub(r"[\s\-().]", "", text)
    if text.startswith("00"):
        text = "+" + text[2:]
    has_plus = text.startswith("+")
    body = re.sub(r"\D", "", text)
    return ("+" + body) if has_plus else body


def _find_national_number(digits: str, country: Country):
    """Try the forms a number can arrive in and return the first one that
    satisfies the country's rule.

    Order matters only in that every candidate is checked against the same
    pattern, so an ambiguous string can never validate as the wrong shape.
    """
    explicit_country_code = digits.startswith("+")
    body = digits.lstrip("+")
    dial = country.dial_digits

    # An explicit +code must be this country's code; +44… under Iran is a
    # mismatch the student should see, not a number silently reinterpreted.
    if explicit_country_code and not body.startswith(dial):
        return None

    candidates = []
    if body.startswith(dial):
        candidates.append(body[len(dial):])
    if not explicit_country_code:
        candidates.append(body)
        if country.trunk_prefix and body.startswith(country.trunk_prefix):
            candidates.append(body[len(country.trunk_prefix):])
    else:
        # +98 0912… — some people keep the trunk zero after the country code.
        trimmed = body[len(dial):]
        if country.trunk_prefix and trimmed.startswith(country.trunk_prefix):
            candidates.append(trimmed[len(country.trunk_prefix):])

    for candidate in candidates:
        if country.accepts(candidate):
            return candidate
    return None
