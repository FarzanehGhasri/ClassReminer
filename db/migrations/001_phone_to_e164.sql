-- Migration 001 — store phone numbers in E.164 so students outside Iran can
-- register through the form.
--
-- Run this against a database created before the registration form existed:
--   docker compose exec -T db psql -U classreminer -d classreminer \
--       -v ON_ERROR_STOP=1 < db/migrations/001_phone_to_e164.sql
--
-- A database created from db/init/01_schema.sql after this change already has
-- the new domain and does not need it. Re-running is harmless: the guard at
-- the top exits early once phone_number is already phone_e164.

BEGIN;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'student' AND column_name = 'phone_number'
          AND domain_name = 'phone_e164'
    ) THEN
        RAISE NOTICE 'phone_number is already phone_e164 — nothing to do';
        RETURN;
    END IF;

    -- The Iranian rule survives the change: any +98 number must still be a
    -- mobile, which is what 09XXXXXXXXX means once written internationally.
    CREATE DOMAIN phone_e164 AS TEXT
        CONSTRAINT phone_e164_check CHECK (
            VALUE ~ '^\+[1-9][0-9]{6,14}$'
            AND (VALUE !~ '^\+98' OR VALUE ~ '^\+989[0-9]{9}$')
        );

    -- enrolment_reminder selects phone_number, and PostgreSQL refuses to
    -- retype a column a view depends on. Drop it, retype, put it back
    -- exactly as db/init/01_schema.sql defines it.
    DROP VIEW IF EXISTS enrolment_reminder;

    -- 09122025452 -> +989122025452. Rows already in E.164 are left alone.
    ALTER TABLE student
        ALTER COLUMN phone_number TYPE phone_e164
        USING CASE
            WHEN phone_number LIKE '+%' THEN phone_number
            WHEN phone_number ~ '^09[0-9]{9}$' THEN '+98' || substring(phone_number FROM 2)
            ELSE phone_number
        END::phone_e164;

    CREATE VIEW enrolment_reminder AS
    SELECT s.id                               AS student_id,
           c.id                               AS class_id,
           s.first_name || ' ' || s.last_name AS full_name,
           s.email,
           s.phone_number,
           s.telegram_chat_id,
           s.bale_chat_id,
           c.class_day,
           c.class_time,
           c.class_link,
           c.delivery_mode,
           c.class_format
    FROM student_class sc
    JOIN student s ON s.id = sc.student_id
    JOIN class   c ON c.id = sc.class_id;

    DROP DOMAIN IF EXISTS iran_mobile;

    COMMENT ON COLUMN student.phone_number IS
        'E.164, e.g. +989122025452. A +98 number must be a valid Iranian mobile.';
END $$;

COMMIT;
