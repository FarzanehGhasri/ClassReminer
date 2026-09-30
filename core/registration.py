"""
The registration use case: turn raw form input into a stored student.

Depends only on the StudentRepository abstraction, so the same service runs
against PostgreSQL in production and against an in-memory fake in tests.
Nothing here knows about HTTP, Flask, or SQL.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional

from core.interfaces.student_repository import DuplicateStudent, StudentRepository
from core.models.country import CountryRegistry
from core.models.student import Student, StudentValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RegistrationResult:
    ok: bool
    student_id: Optional[int] = None
    full_name: str = ""
    errors: Optional[Dict[str, str]] = None

    @staticmethod
    def success(student_id: int, full_name: str) -> "RegistrationResult":
        return RegistrationResult(ok=True, student_id=student_id, full_name=full_name)

    @staticmethod
    def failure(errors: Dict[str, str]) -> "RegistrationResult":
        return RegistrationResult(ok=False, errors=errors)


class RegistrationService:
    def __init__(self, repository: StudentRepository, countries: CountryRegistry):
        self._repository = repository
        self._countries = countries

    def register(
        self,
        first_name: str,
        last_name: str,
        phone_raw: str,
        email: str,
        country_iso: str,
    ) -> RegistrationResult:
        country = self._countries.get(country_iso)

        try:
            student = Student.create(first_name, last_name, phone_raw, email, country)
        except StudentValidationError as error:
            return RegistrationResult.failure(error.errors)

        try:
            student_id = self._repository.add(student)
        except DuplicateStudent as error:
            return RegistrationResult.failure({error.field: error.message})

        # The number and address are what identify a person here, so they stay
        # out of the log; the id is enough to find the row.
        logger.info("Registered student id=%s", student_id)
        return RegistrationResult.success(student_id, student.full_name)
