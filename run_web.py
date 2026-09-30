"""
Composition root for the registration form, the counterpart to main.py.

main.py wires the reminder job; this wires the web form. Both build concrete
classes here and nowhere else.

Development:
    python3 run_web.py
Production (a real WSGI server, not Flask's):
    gunicorn --bind 0.0.0.0:8000 'run_web:application'
"""
from config import settings
from core.models.country import CountryRegistry
from core.registration import RegistrationService
from infrastructure.postgres_student_writer import PostgresStudentWriter
from utils.logger import setup_logging
from web.app import create_app


def build_app():
    # Called here rather than under __main__ so gunicorn, which imports this
    # module and never runs __main__, still gets configured logging.
    setup_logging()

    countries = CountryRegistry()
    repository = PostgresStudentWriter(
        settings.postgres_dsn(),
        connect_timeout=settings.POSTGRES_CONNECT_TIMEOUT,
    )
    registration = RegistrationService(repository, countries)
    return create_app(registration, countries)


application = build_app()

if __name__ == "__main__":
    application.run(host=settings.WEB_HOST, port=settings.WEB_PORT, debug=False)
