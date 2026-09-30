#!/usr/bin/env python3
"""
One-off migration: move the rows in data/*.csv into the PostgreSQL tables.

Runs as a dry run by default and prints exactly what it would do; pass
--commit to write. Rows that fail validation are reported and skipped, never
silently repaired — a student with a Latin name or a malformed phone number
needs a human decision, not a guess.

    python3 scripts/import_students_csv.py data/students.csv
    python3 scripts/import_students_csv.py data/students.csv --commit

Supported columns (extras are ignored, missing optional ones are fine):
    first_name, last_name   or   name  ("مهزیار گیلانپور" — split on the space)
    phone_number, email
    schedule_weekday, schedule_time, message_link   -> a class + enrolment
    delivery_mode, class_format                     -> default online / group
    telegram_chat_id, bale_chat_id
    country                                         -> ISO code, defaults to IR

Rows are validated by core.models.Student, the same entity the registration
form builds, so the CSV path and the web path cannot disagree about what a
valid student is.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg

from config import settings
from core.models.country import CountryRegistry
from core.models.student import Student, StudentValidationError


def split_name(row: dict) -> tuple:
    """first_name/last_name if present, else split `name` on whitespace."""
    first = (row.get("first_name") or "").strip()
    last = (row.get("last_name") or "").strip()
    if first or last:
        return first, last

    parts = (row.get("name") or "").strip().split()
    if len(parts) >= 2:
        # Everything after the first token is the family name (e.g. آل احمد).
        return parts[0], " ".join(parts[1:])
    return (parts[0] if parts else ""), ""


def upsert_student(cur, student, row: dict) -> int:
    cur.execute(
        """
        INSERT INTO student (first_name, last_name, phone_number, email,
                             telegram_chat_id, bale_chat_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (phone_number) DO UPDATE
            SET first_name       = EXCLUDED.first_name,
                last_name        = EXCLUDED.last_name,
                email            = EXCLUDED.email,
                telegram_chat_id = COALESCE(EXCLUDED.telegram_chat_id, student.telegram_chat_id),
                bale_chat_id     = COALESCE(EXCLUDED.bale_chat_id, student.bale_chat_id)
        RETURNING id
        """,
        (
            student.first_name,
            student.last_name,
            student.phone.e164,
            student.email,
            (row.get("telegram_chat_id") or "").strip() or None,
            (row.get("bale_chat_id") or "").strip() or None,
        ),
    )
    return cur.fetchone()[0]


def upsert_class(cur, row: dict):
    """Find or create the class this row describes. Returns None when the row
    carries no schedule (a registration with no class assigned yet)."""
    weekday = (row.get("schedule_weekday") or "").strip().lower()
    class_time = (row.get("schedule_time") or "").strip()
    if not weekday or not class_time:
        return None

    link = (row.get("message_link") or "").strip() or None
    mode = (row.get("delivery_mode") or "").strip() or ("online" if link else "in_person")
    fmt = (row.get("class_format") or "").strip() or "group"

    # Identical day/time/link is the same class, not a second one.
    cur.execute(
        """
        SELECT id FROM class
        WHERE class_day = %s AND class_time = %s
          AND class_link IS NOT DISTINCT FROM %s
        """,
        (weekday, class_time, link),
    )
    found = cur.fetchone()
    if found:
        return found[0]

    cur.execute(
        """
        INSERT INTO class (class_day, class_time, class_link, delivery_mode, class_format)
        VALUES (%s, %s, %s, %s, %s) RETURNING id
        """,
        (weekday, class_time, link, mode, fmt),
    )
    return cur.fetchone()[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--commit", action="store_true",
                        help="actually write; without it nothing is saved")
    args = parser.parse_args()

    if not args.csv_path.exists():
        print(f"no such file: {args.csv_path}", file=sys.stderr)
        return 1

    # utf-8-sig strips the BOM that Excel leaves on the first header.
    with args.csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    imported, enrolled, skipped = 0, 0, []
    countries = CountryRegistry()

    with psycopg.connect(settings.postgres_dsn()) as conn:
        with conn.cursor() as cur:
            for line_number, row in enumerate(rows, start=2):
                first, last = split_name(row)
                iso = (row.get("country") or "").strip() or countries.default.iso
                try:
                    student = Student.create(
                        first, last, row.get("phone_number", ""), row.get("email", ""),
                        countries.get(iso),
                    )
                except StudentValidationError as error:
                    label = row.get("name") or f"{first} {last}".strip()
                    skipped.append((line_number, label, list(error.errors.values())))
                    continue

                try:
                    student_id = upsert_student(cur, student, row)
                    class_id = upsert_class(cur, row)
                    if class_id is not None:
                        cur.execute(
                            """INSERT INTO student_class (student_id, class_id)
                               VALUES (%s, %s) ON CONFLICT DO NOTHING""",
                            (student_id, class_id),
                        )
                        enrolled += cur.rowcount
                    imported += 1
                except psycopg.Error as error:
                    # Savepoint-free: one bad row would poison the transaction,
                    # so report it and stop rather than commit a half import.
                    print(f"row {line_number}: {str(error).strip()}", file=sys.stderr)
                    conn.rollback()
                    return 1

        if args.commit:
            conn.commit()
        else:
            conn.rollback()

    print(f"{'imported' if args.commit else 'would import'}: "
          f"{imported} student(s), {enrolled} enrolment(s)")

    if skipped:
        print(f"\nskipped {len(skipped)} row(s) needing a human decision:")
        for line_number, label, problems in skipped:
            print(f"  line {line_number} ({label}):")
            for problem in problems:
                print(f"      - {problem}")
        print("\nFix these in the CSV (Persian first_name/last_name columns are the")
        print("usual culprit) and re-run, or add them by hand with psql.")

    if not args.commit:
        print("\nDry run — nothing was written. Re-run with --commit to save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
