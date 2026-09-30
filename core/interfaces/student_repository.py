from abc import ABC, abstractmethod

from core.models.student import Student


class DuplicateStudent(Exception):
    """The phone number or e-mail already belongs to a registered student.

    A domain-level exception, so the registration service never has to know
    what a psycopg IntegrityError is."""

    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)


class StudentRepository(ABC):
    """Writing a student down. Deliberately separate from RecipientRepository,
    which reads enrolments for the reminder job: a registration form has no
    use for load_all, and the scheduler has no use for add. Two small
    interfaces beat one that forces either side to stub a method out."""

    @abstractmethod
    def add(self, student: Student) -> int:
        """Persist the student and return the new id.
        Raises DuplicateStudent if the phone or e-mail is already taken."""
        ...
