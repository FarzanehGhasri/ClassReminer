"""
Concrete StudentRepository backed by PostgreSQL.

The only place in the registration path that knows SQL exists. It also
translates psycopg's unique-violation into the domain's DuplicateStudent, so
nothing above this layer imports a database exception.
"""
import logging

import psycopg
from psycopg import errors as pg_errors

from core.interfaces.student_repository import DuplicateStudent, StudentRepository
from core.models.student import Student

logger = logging.getLogger(__name__)

_INSERT = """
    INSERT INTO student (first_name, last_name, phone_number, email)
    VALUES (%s, %s, %s, %s)
    RETURNING id
"""

# Which domain rejected the value decides which field the form highlights.
_CHECK_TO_FIELD = {
    "persian_name_check": "first_name",
    "phone_e164_check": "phone",
    "email_address_check": "email",
}

# Which unique constraint tripped decides which field the form highlights.
_CONSTRAINT_TO_FIELD = {
    "student_phone_number_key": ("phone", "این شماره تماس قبلاً ثبت شده است."),
    "student_email_lower_key": ("email", "این ایمیل قبلاً ثبت شده است."),
}


class PostgresStudentWriter(StudentRepository):
    def __init__(self, dsn: str, connect_timeout: int = 10):
        self._dsn = dsn
        self._connect_timeout = connect_timeout

    def add(self, student: Student) -> int:
        try:
            with psycopg.connect(self._dsn, connect_timeout=self._connect_timeout) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        _INSERT,
                        (
                            student.first_name,
                            student.last_name,
                            student.phone.e164,
                            student.email,
                        ),
                    )
                    return cur.fetchone()[0]
        except pg_errors.CheckViolation as error:
            # Reached only if a validation rule here drifts out of step with the
            # SQL domains. The student sees a field error rather than a crash,
            # and the log carries the constraint name so the drift gets fixed.
            constraint = getattr(error.diag, "constraint_name", "") or "unknown"
            logger.error("Student rejected by database constraint %s", constraint)
            raise DuplicateStudent(
                _CHECK_TO_FIELD.get(constraint, "form"),
                "مقدار واردشده معتبر نیست.",
            ) from error
        except pg_errors.UniqueViolation as error:
            field, message = _CONSTRAINT_TO_FIELD.get(
                getattr(error.diag, "constraint_name", "") or "",
                ("phone", "این مشخصات قبلاً ثبت شده است."),
            )
            raise DuplicateStudent(field, message) from error
