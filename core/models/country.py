"""
The country registry: one Country per dialling code, each carrying the rule
its mobile numbers must satisfy.

Open/Closed lives here. Supporting a new country is one entry in COUNTRIES —
no validator, no form template and no SQL changes. Nothing else in the
codebase knows a country by name.
"""
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Country:
    iso: str              # ISO 3166-1 alpha-2, the value the form posts back
    dial_code: str        # "+98" — what gets stored in front of the number
    name_fa: str          # shown in the picker
    flag: str
    national_pattern: str # the national significant number, trunk prefix removed
    trunk_prefix: str     # "0" where the country uses one, "" where it does not
    example_local: str    # how a local would write it, shown under the field
    hint_fa: str          # the rule, in Persian, shown under the field

    @property
    def dial_digits(self) -> str:
        return self.dial_code.lstrip("+")

    def accepts(self, national_number: str) -> bool:
        return bool(re.fullmatch(self.national_pattern, national_number))

    def as_dict(self) -> dict:
        """Serialised to the browser so the form's live hints and the server's
        validation read from one source instead of two copies that drift."""
        return {
            "iso": self.iso,
            "dial_code": self.dial_code,
            "name_fa": self.name_fa,
            "flag": self.flag,
            "national_pattern": self.national_pattern,
            "trunk_prefix": self.trunk_prefix,
            "example_local": self.example_local,
            "hint_fa": self.hint_fa,
        }


# Mobile rules only — these are the numbers a class reminder can reach.
# Landlines are deliberately rejected.
COUNTRIES: Tuple[Country, ...] = (
    Country("IR", "+98",  "ایران",            "🇮🇷", r"9\d{9}",                        "0",
            "0912 345 6789",  "با ۰۹ شروع شود و ۱۱ رقم باشد"),
    Country("TR", "+90",  "ترکیه",             "🇹🇷", r"5\d{9}",                        "0",
            "0532 123 4567",  "با ۰۵ شروع شود و ۱۱ رقم باشد"),
    Country("AE", "+971", "امارات",            "🇦🇪", r"5[024-68]\d{7}",                "0",
            "050 123 4567",   "با ۰۵ شروع شود و ۱۰ رقم باشد"),
    Country("IQ", "+964", "عراق",              "🇮🇶", r"7[3-9]\d{8}",                   "0",
            "0770 123 4567",  "با ۰۷ شروع شود و ۱۱ رقم باشد"),
    Country("GB", "+44",  "بریتانیا",          "🇬🇧", r"7[1-9]\d{8}",                   "0",
            "07400 123456",   "با ۰۷ شروع شود و ۱۱ رقم باشد"),
    Country("DE", "+49",  "آلمان",             "🇩🇪", r"1[5-7]\d{8,9}",                 "0",
            "0151 23456789",  "با ۰۱۵ تا ۰۱۷ شروع شود"),
    Country("US", "+1",   "آمریکا / کانادا",   "🇺🇸", r"[2-9]\d{9}",                    "",
            "(415) 555-0123", "۱۰ رقم، بدون صفر ابتدایی"),
    Country("SE", "+46",  "سوئد",              "🇸🇪", r"7[02369]\d{7}",                 "0",
            "070 123 45 67",  "با ۰۷ شروع شود و ۱۰ رقم باشد"),
    Country("NL", "+31",  "هلند",              "🇳🇱", r"6\d{8}",                        "0",
            "06 12345678",    "با ۰۶ شروع شود و ۱۰ رقم باشد"),
    Country("FR", "+33",  "فرانسه",            "🇫🇷", r"[67]\d{8}",                     "0",
            "06 12 34 56 78", "با ۰۶ یا ۰۷ شروع شود و ۱۰ رقم باشد"),
    Country("AU", "+61",  "استرالیا",          "🇦🇺", r"4\d{8}",                        "0",
            "0412 345 678",   "با ۰۴ شروع شود و ۱۰ رقم باشد"),
    Country("AZ", "+994", "آذربایجان",         "🇦🇿", r"(?:40|50|51|55|60|70|77|99)\d{7}", "0",
            "050 123 45 67",  "با ۰۵ یا ۰۷ شروع شود و ۱۰ رقم باشد"),
    Country("AM", "+374", "ارمنستان",          "🇦🇲", r"[3-9]\d{7}",                    "0",
            "077 123456",     "۸ رقم پس از کد کشور"),
    Country("GE", "+995", "گرجستان",           "🇬🇪", r"5\d{8}",                        "",
            "555 123 456",    "با ۵ شروع شود و ۹ رقم باشد"),
    Country("QA", "+974", "قطر",               "🇶🇦", r"[3567]\d{7}",                   "",
            "3312 3456",      "۸ رقم، بدون صفر ابتدایی"),
    Country("OM", "+968", "عمان",              "🇴🇲", r"9\d{7}",                        "",
            "9123 4567",      "با ۹ شروع شود و ۸ رقم باشد"),
    Country("KW", "+965", "کویت",              "🇰🇼", r"[569]\d{7}",                    "",
            "9123 4567",      "۸ رقم، بدون صفر ابتدایی"),
    Country("AF", "+93",  "افغانستان",         "🇦🇫", r"7\d{8}",                        "0",
            "070 123 4567",   "با ۰۷ شروع شود و ۱۰ رقم باشد"),
)

DEFAULT_COUNTRY_ISO = "IR"


class CountryRegistry:
    """Lookup over the countries the form offers.

    Injected wherever a country is needed, so a test can hand in a two-country
    registry and a deployment could hand in a different list entirely."""

    def __init__(self, countries=COUNTRIES, default_iso: str = DEFAULT_COUNTRY_ISO):
        self._countries: Tuple[Country, ...] = tuple(countries)
        self._by_iso: Dict[str, Country] = {c.iso: c for c in self._countries}
        if default_iso not in self._by_iso:
            raise ValueError(f"default country {default_iso!r} is not in the registry")
        self._default_iso = default_iso

    def all(self) -> List[Country]:
        return list(self._countries)

    def get(self, iso: Optional[str]) -> Optional[Country]:
        if not iso:
            return None
        return self._by_iso.get(iso.strip().upper())

    @property
    def default(self) -> Country:
        return self._by_iso[self._default_iso]

    def as_list(self) -> List[dict]:
        return [c.as_dict() for c in self._countries]
