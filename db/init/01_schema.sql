-- ClassReminer schema — PostgreSQL
--
-- Three relations:
--   student        one row per person
--   class          one row per recurring class slot
--   student_class  the many-to-many bridge (an enrolment)
--
-- A group class is simply a class row that several student_class rows point at.
-- A private class is a class row that exactly one student_class row points at
-- (enforced by the trigger at the bottom of this file).

BEGIN;

-- ---------------------------------------------------------------------------
-- Reusable value domains: the validation rules live in the database, so no
-- application bug can slip a malformed phone number or e-mail past them.
-- ---------------------------------------------------------------------------

-- Persian letters (Arabic block + the Persian-specific پ چ ژ ک گ ی),
-- separated by a space, a hyphen, or ZWNJ (U+200C, the نیم‌فاصله).
-- The shape is LETTER+ (SEPARATOR LETTER+)* so a name can neither be blank
-- nor start/end with a separator, and Latin letters and digits are rejected.
CREATE DOMAIN persian_name AS TEXT
    CONSTRAINT persian_name_check CHECK (
        VALUE ~ '^[\u0621-\u063A\u0641-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06BE\u06CC]+([ \u200C-][\u0621-\u063A\u0641-\u064A\u067E\u0686\u0698\u06A9\u06AF\u06BE\u06CC]+)*$'
    );

-- Iranian mobile number: starts with 09, exactly 11 digits in total.
CREATE DOMAIN iran_mobile AS TEXT
    CONSTRAINT iran_mobile_check CHECK (VALUE ~ '^09[0-9]{9}$');

-- Deliberately pragmatic: one @, a dot-bearing domain, no whitespace.
-- A regex cannot prove an address is deliverable; that is what the
-- confirmation e-mail is for.
CREATE DOMAIN email_address AS TEXT
    CONSTRAINT email_address_check CHECK (
        VALUE ~ '^[A-Za-z0-9!#$%&''*+/=?^_`{|}~.-]+@[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?)+$'
        AND VALUE !~ '\.\.'
        AND length(VALUE) <= 254
    );

CREATE TYPE weekday AS ENUM (
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
);

-- How the class is attended.
CREATE TYPE delivery_mode AS ENUM ('online', 'in_person');

-- How many students the class is sold to.
CREATE TYPE class_format AS ENUM ('private', 'group');

-- ---------------------------------------------------------------------------
-- student
-- ---------------------------------------------------------------------------

CREATE TABLE student (
    id               SERIAL PRIMARY KEY,
    first_name       persian_name  NOT NULL,
    last_name        persian_name  NOT NULL,
    phone_number     iran_mobile   NOT NULL UNIQUE,
    email            email_address NOT NULL,

    -- Chat handles for the Telegram and Bale channels. Same functional
    -- dependency as phone_number and email (id -> handle), so they belong
    -- in this table rather than a separate contacts relation.
    telegram_chat_id TEXT,
    bale_chat_id     TEXT,

    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT telegram_chat_id_not_blank CHECK (telegram_chat_id <> ''),
    CONSTRAINT bale_chat_id_not_blank     CHECK (bale_chat_id <> '')
);

-- Addresses differing only in case are the same mailbox in practice.
CREATE UNIQUE INDEX student_email_lower_key ON student (lower(email));

COMMENT ON TABLE  student IS 'One row per person who receives class reminders.';
COMMENT ON COLUMN student.phone_number IS 'Iranian mobile, 09XXXXXXXXX (11 digits).';

-- ---------------------------------------------------------------------------
-- class
-- ---------------------------------------------------------------------------

CREATE TABLE class (
    id          SERIAL PRIMARY KEY,
    class_day   weekday       NOT NULL,
    class_time  TIME          NOT NULL,
    class_link  TEXT,
    delivery_mode delivery_mode NOT NULL,
    class_format  class_format  NOT NULL,
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now(),

    -- An online class without a join link cannot be attended.
    CONSTRAINT online_class_needs_link
        CHECK (delivery_mode <> 'online' OR class_link IS NOT NULL),

    -- Whatever link is stored must at least be a URL.
    CONSTRAINT class_link_is_url
        CHECK (class_link IS NULL OR class_link ~ '^https?://[^[:space:]]+$')
);

CREATE INDEX class_day_time_idx ON class (class_day, class_time);

COMMENT ON COLUMN class.delivery_mode IS 'online | in_person — how the class is attended.';
COMMENT ON COLUMN class.class_format  IS 'private | group — a group class is shared by several students.';

-- ---------------------------------------------------------------------------
-- student_class — the enrolment bridge
-- ---------------------------------------------------------------------------

CREATE TABLE student_class (
    student_id  INTEGER     NOT NULL REFERENCES student (id) ON DELETE CASCADE,
    class_id    INTEGER     NOT NULL REFERENCES class (id)   ON DELETE CASCADE,
    enrolled_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (student_id, class_id)
);

-- The primary key already indexes (student_id, class_id); this one serves
-- the reverse lookup "who is in class X?".
CREATE INDEX student_class_class_id_idx ON student_class (class_id);

COMMENT ON TABLE student_class IS
    'Many-to-many: a student attends many classes, a class holds many students.';

-- ---------------------------------------------------------------------------
-- A private class may hold only one student. A group class is unbounded.
-- This is the one rule the key structure cannot express on its own.
-- ---------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION enforce_private_class_capacity() RETURNS TRIGGER AS $$
DECLARE
    class_is_private BOOLEAN;
    already_enrolled INTEGER;
BEGIN
    -- FOR SHARE keeps a concurrent enrolment from slipping in past the count.
    SELECT class_format = 'private' INTO class_is_private
    FROM class WHERE id = NEW.class_id FOR SHARE;

    IF NOT class_is_private THEN
        RETURN NEW;
    END IF;

    SELECT count(*) INTO already_enrolled
    FROM student_class
    WHERE class_id = NEW.class_id AND student_id <> NEW.student_id;

    IF already_enrolled > 0 THEN
        RAISE EXCEPTION
            'class % is private and already has a student; only a group class can be shared',
            NEW.class_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER student_class_private_capacity
    BEFORE INSERT OR UPDATE ON student_class
    FOR EACH ROW EXECUTE FUNCTION enforce_private_class_capacity();

-- ---------------------------------------------------------------------------
-- What the reminder job reads: one row per (student, class) enrolment.
-- ---------------------------------------------------------------------------

CREATE VIEW enrolment_reminder AS
SELECT s.id                            AS student_id,
       c.id                            AS class_id,
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

COMMIT;
