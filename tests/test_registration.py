"""
Tests for the registration path.

Everything here runs without a database: RegistrationService depends on the
StudentRepository abstraction, so an in-memory fake substitutes for PostgreSQL.
That substitutability is the Liskov and Dependency Inversion claim made
concrete — if these pass against the fake, the service logic is correct
independently of what stores the rows.

    python3 -m unittest discover -s tests -v
"""
import unittest

from core.interfaces.student_repository import DuplicateStudent, StudentRepository
from core.models.country import Country, CountryRegistry
from core.models.phone_number import InvalidPhoneNumber, PhoneNumber
from core.models.student import Student, StudentValidationError
from core.registration import RegistrationService


class InMemoryStudentRepository(StudentRepository):
    def __init__(self):
        self.students = []
        self._phones = set()
        self._emails = set()

    def add(self, student: Student) -> int:
        if student.phone.e164 in self._phones:
            raise DuplicateStudent("phone", "این شماره تماس قبلاً ثبت شده است.")
        if student.email.lower() in self._emails:
            raise DuplicateStudent("email", "این ایمیل قبلاً ثبت شده است.")
        self._phones.add(student.phone.e164)
        self._emails.add(student.email.lower())
        self.students.append(student)
        return len(self.students)


class PhoneNumberTests(unittest.TestCase):
    def setUp(self):
        self.countries = CountryRegistry()
        self.iran = self.countries.get("IR")

    def test_every_way_an_iranian_number_is_written_normalises_the_same(self):
        for raw in [
            "09122025452", "9122025452", "+989122025452", "۰۹۱۲۲۰۲۵۴۵۲",
            "0912-202-5452", "0912 202 5452", "0098 912 202 5452",
            "+98 912 202 5452", "+98 0912 202 5452", "(0912) 202-5452",
        ]:
            with self.subTest(raw=raw):
                self.assertEqual(PhoneNumber.parse(raw, self.iran).e164, "+989122025452")

    def test_iranian_rule_still_rejects_non_mobiles_and_wrong_lengths(self):
        for raw in ["08122025452", "0912202545", "091220254521", "02112345678"]:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidPhoneNumber):
                    PhoneNumber.parse(raw, self.iran)

    def test_a_number_from_another_country_is_not_reinterpreted(self):
        with self.assertRaises(InvalidPhoneNumber):
            PhoneNumber.parse("+447400123456", self.iran)

    def test_other_countries_use_their_own_rule(self):
        cases = [
            ("GB", "07400 123456", "+447400123456"),
            ("US", "(415) 555-0123", "+14155550123"),
            ("TR", "0532 123 4567", "+905321234567"),
            ("DE", "+49 151 23456789", "+4915123456789"),
            ("AE", "050 123 4567", "+971501234567"),
        ]
        for iso, raw, expected in cases:
            with self.subTest(iso=iso):
                self.assertEqual(
                    PhoneNumber.parse(raw, self.countries.get(iso)).e164, expected
                )

    def test_local_format_round_trips(self):
        self.assertEqual(
            PhoneNumber.parse("+989122025452", self.iran).local_format, "09122025452"
        )

    def test_a_new_country_needs_no_code_change(self):
        """Open/Closed: the registry takes an extra entry and everything works."""
        norway = Country("NO", "+47", "نروژ", "🇳🇴", r"[49]\d{7}", "",
                         "412 34 567", "۸ رقم")
        registry = CountryRegistry(CountryRegistry().all() + [norway])
        self.assertEqual(
            PhoneNumber.parse("41234567", registry.get("NO")).e164, "+4741234567"
        )


class StudentValidationTests(unittest.TestCase):
    def setUp(self):
        self.countries = CountryRegistry()
        self.iran = self.countries.get("IR")

    def test_a_valid_student_is_built(self):
        student = Student.create("سارا", "احمدی", "09123456789",
                                 "sara@example.com", self.iran)
        self.assertEqual(student.full_name, "سارا احمدی")
        self.assertEqual(student.phone.e164, "+989123456789")

    def test_persian_names_with_zwnj_and_hyphen_are_accepted(self):
        for first, last in [("نیلوفر", "حسین‌زاده"), ("محمد رضا", "آل-احمد")]:
            with self.subTest(last=last):
                Student.create(first, last, "09123456789", "a@b.com", self.iran)

    def test_latin_names_are_rejected(self):
        with self.assertRaises(StudentValidationError) as ctx:
            Student.create("Sara", "Ahmadi", "09123456789", "a@b.com", self.iran)
        self.assertIn("first_name", ctx.exception.errors)
        self.assertIn("last_name", ctx.exception.errors)

    def test_every_bad_field_is_reported_in_one_pass(self):
        with self.assertRaises(StudentValidationError) as ctx:
            Student.create("Sara", "", "08122025452", "not-an-email", self.iran)
        self.assertEqual(
            set(ctx.exception.errors), {"first_name", "last_name", "phone", "email"}
        )

    def test_email_matches_what_the_database_accepts(self):
        """These are exactly the addresses the email_address SQL domain refuses.
        Accepting one here would turn a field error into a 500."""
        for email in ["lkj;lj@gmail.com", "a@gmail", "a..b@x.com",
                      "a b@x.com", "a@gmail-.com"]:
            with self.subTest(email=email):
                with self.assertRaises(StudentValidationError) as ctx:
                    Student.create("سارا", "احمدی", "09123456789", email, self.iran)
                self.assertIn("email", ctx.exception.errors)

    def test_missing_country_is_a_field_error_not_a_crash(self):
        with self.assertRaises(StudentValidationError) as ctx:
            Student.create("سارا", "احمدی", "09123456789", "a@b.com", None)
        self.assertIn("country", ctx.exception.errors)


class RegistrationServiceTests(unittest.TestCase):
    def setUp(self):
        self.repository = InMemoryStudentRepository()
        self.service = RegistrationService(self.repository, CountryRegistry())

    def register(self, **overrides):
        payload = dict(first_name="سارا", last_name="احمدی", phone_raw="09123456789",
                       email="sara@example.com", country_iso="IR")
        payload.update(overrides)
        return self.service.register(**payload)

    def test_a_good_registration_is_stored(self):
        result = self.register()
        self.assertTrue(result.ok)
        self.assertEqual(result.full_name, "سارا احمدی")
        self.assertEqual(len(self.repository.students), 1)

    def test_nothing_is_stored_when_validation_fails(self):
        result = self.register(first_name="Sara")
        self.assertFalse(result.ok)
        self.assertIn("first_name", result.errors)
        self.assertEqual(self.repository.students, [])

    def test_duplicate_phone_is_a_field_error(self):
        self.register()
        result = self.register(email="other@example.com")
        self.assertFalse(result.ok)
        self.assertIn("phone", result.errors)

    def test_duplicate_email_is_a_field_error(self):
        self.register()
        result = self.register(phone_raw="09121110000")
        self.assertFalse(result.ok)
        self.assertIn("email", result.errors)

    def test_unknown_country_is_rejected(self):
        result = self.register(country_iso="ZZ")
        self.assertFalse(result.ok)
        self.assertIn("country", result.errors)


if __name__ == "__main__":
    unittest.main()
