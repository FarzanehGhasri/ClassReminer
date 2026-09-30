# ClassReminer database

PostgreSQL 16 in Docker, three relations, all validation enforced by the
database rather than trusted to the application.

```
student ──────< student_class >────── class
   1                  M:N                1
```

## Running it

```bash
cp .env.example .env          # edit POSTGRES_PASSWORD at least
docker compose up -d
docker compose logs -f db     # wait for "database system is ready"
```

`db/init/*.sql` runs once, in filename order, the first time the volume is
created — `01_schema.sql` then `02_seed.sql`. To re-apply after editing the
schema you have to drop the volume, which deletes all data:

```bash
docker compose down -v && docker compose up -d
```

## Looking at the data

PostgreSQL has no web interface of its own. Port 5432 speaks the PostgreSQL
wire protocol, not HTTP, so opening `http://localhost:5432` in a browser
returns an empty response — that error means the server is running, not that
something is broken. Reading the data needs a client.

**Terminal.** No password needed; connections over the container's own socket
are trusted:

```bash
docker compose exec db psql -U classreminer -d classreminer
```

Useful once inside: `\dt` lists tables, `\d student` describes one, `\dv`
lists views, `\q` quits.

**Browser.** `docker compose up -d` also starts Adminer on
<http://localhost:8080>. Log in with:

| Field | Value |
| --- | --- |
| System | PostgreSQL |
| Server | `db` (pre-filled) |
| Username | `classreminer` |
| Password | whatever `POSTGRES_PASSWORD` is in `.env` |
| Database | `classreminer` |

Server is `db`, not `localhost`: inside the Docker network, containers reach
each other by service name. `localhost` from Adminer's point of view is the
Adminer container itself.

Adminer is bound to `127.0.0.1`, so it is reachable only from the machine
running Docker. It asks for the database password, but it is still an
administrative tool — do not publish it. On a server, either delete the
service from `docker-compose.yml` or reach it through an SSH tunnel:

```bash
ssh -L 8080:127.0.0.1:8080 you@your-server
```

**Desktop client.** TablePlus, DBeaver or pgAdmin. Connect to host
`localhost`, port `5432`, database `classreminer`, user `classreminer`, and
the password from `.env`. Here the host *is* `localhost`, because the client
runs on your machine and reaches Postgres through the published port.

Then point the reminder job at it (`.env`):

```
RECIPIENT_SOURCE=postgres
```

`RECIPIENT_SOURCE=csv` still selects the old `data/students.csv` path, so the
switch is reversible.

## Tables

### `student`

| column | type | notes |
| --- | --- | --- |
| `id` | `serial` | PK |
| `first_name` | `persian_name` | must be Persian letters |
| `last_name` | `persian_name` | must be Persian letters |
| `phone_number` | `phone_e164` | `+989122025452`, UNIQUE. A `+98` number must be a valid Iranian mobile. |
| `email` | `email_address` | UNIQUE on `lower(email)` |
| `telegram_chat_id` | `text` | nullable, for the Telegram channel |
| `bale_chat_id` | `text` | nullable, for the Bale channel |
| `created_at` | `timestamptz` | defaults to `now()` |

`telegram_chat_id` and `bale_chat_id` are not in the original three-column
sketch, but the Telegram and Bale channels read them — dropping them would
have left only e-mail working. They have the same functional dependency as
`phone_number` (`id → handle`), so they belong in this table.

### `class`

| column | type | notes |
| --- | --- | --- |
| `id` | `serial` | PK |
| `class_day` | `weekday` | enum, `monday`…`sunday` |
| `class_time` | `time` | |
| `class_link` | `text` | required when `delivery_mode = 'online'` |
| `delivery_mode` | `delivery_mode` | enum, `online` \| `in_person` |
| `class_format` | `class_format` | enum, `private` \| `group` |
| `created_at` | `timestamptz` | |

Two columns were unnamed in the request; they are `delivery_mode` (how the
class is attended) and `class_format` (how it is sold).

### `student_class`

| column | type | notes |
| --- | --- | --- |
| `student_id` | `integer` | FK → `student(id)`, `ON DELETE CASCADE` |
| `class_id` | `integer` | FK → `class(id)`, `ON DELETE CASCADE` |
| `enrolled_at` | `timestamptz` | |

Primary key is `(student_id, class_id)`, which both prevents enrolling the
same student twice and lets several students share one `class_id` — the
group-class case. A trigger (`enforce_private_class_capacity`) refuses a
second student on a class whose `class_format` is `private`.

## Validation rules

| rule | where | rejects |
| --- | --- | --- |
| Persian names | `persian_name` domain | `Dorsa`, `درسا۱`, `درساDorsa`, blanks, leading/trailing separators |
| Phone number | `phone_e164` domain | `09122025452` (local form), `+988122025452`, wrong length, letters |
| E-mail | `email_address` domain | no `@`, no TLD, `lkj;lj@gmail.com`, spaces, `a..b@`, trailing-dash domain |
| Online class needs a link | `CHECK` on `class` | `delivery_mode='online'` with `class_link IS NULL` |
| Link is a URL | `CHECK` on `class` | `meet.google.com/xyz` (no scheme) |
| Private class holds one student | trigger on `student_class` | a second enrolment into a private class |

Persian names accept a space, a hyphen, and ZWNJ (U+200C, نیم‌فاصله), so
`حسین‌زاده` and `آل-احمد` are valid.

`utils/validator.py` mirrors these rules in Python so the application can
reject input early with a readable message. The database remains the
authority — the Python copy is a convenience, not the guarantee.

Phone numbers are stored in E.164 and normalised before insert by
`core/models/phone_number.py`: Persian digits, spaces, dashes, `+98`/`0098`
prefixes and a missing leading zero all fold into `+989XXXXXXXXX`. The
per-country rules live in `core/models/country.py`. See `docs/REGISTRATION.md`.

An existing database created before this change is migrated with
`db/migrations/001_phone_to_e164.sql`.

## Importing the old CSVs

```bash
python3 scripts/import_students_csv.py data/students.csv           # dry run
python3 scripts/import_students_csv.py data/students.csv --commit
```

The script validates every row, reports the ones it cannot import, and
writes nothing without `--commit`. Both existing CSVs are rejected in full
because their names are Latin (`DorsaGhasri`) or have no family name — add
`first_name` / `last_name` columns in Persian and re-run.

## Is this in normal form?

Yes — the three tables satisfy 1NF through BCNF, and 4NF. The reasoning,
and the two places where it would stop being true as the schema grows:

**1NF** (atomic values, no repeating groups). Holds. Splitting `first_name`
from `last_name` is part of it — a single `name` column holding two facts is
the usual 1NF slip, and it is why the CSV rows do not import.

**2NF** (no partial dependency on part of a composite key). `student` and
`class` are keyed by a single column, so 2NF cannot be violated there.
`student_class` is the only composite key, and its one non-key attribute
`enrolled_at` depends on *both* halves — when did *this* student join *this*
class. Holds.

**3NF** (no non-key attribute determined by another non-key attribute).
Holds. In `student`, knowing a phone number tells you nothing about the
e-mail; in `class`, no column determines another. The near-miss is
`delivery_mode` and `class_link`: online classes must have a link, but
knowing `delivery_mode = 'online'` does not tell you *which* link, so that
is an existence constraint (a `CHECK`), not a functional dependency.

**BCNF** (every determinant is a candidate key). Holds. `student` has three
candidate keys — `id`, `phone_number`, `lower(email)` — and each determines
the whole row; nothing non-key determines anything.

**4NF** (no independent multi-valued facts in one relation). Holds, and this
is the part `student_class` earns. A student has many classes and a class has
many students; putting either as a repeating group in the other table is the
classic 4NF violation. Resolving it into a bridge table is the fix, and it is
also what makes the shared-`class_id` group case work without redundancy.

One thing that looks redundant but is not: `class_format` could be inferred
from `COUNT(*)` on `student_class`. It should still be stored, because it is a
different fact — what the class *is*, not how many happen to be enrolled. A
group class with one student today is still a group class, and without the
column you could not tell it apart from a private one.

### Where it would stop holding

**A class that meets more than once a week breaks 1NF.** `class_day` holds
one day. A class on Sunday *and* Tuesday forces either `'sunday,tuesday'` in
one column (a 1NF violation) or two `class` rows duplicating the link, mode
and format — an update anomaly, since changing the meeting link then means
changing both rows and getting it wrong is possible. The fix, when you need
it, is a child table:

```sql
CREATE TABLE class_session (
    class_id   INTEGER NOT NULL REFERENCES class(id) ON DELETE CASCADE,
    class_day  weekday NOT NULL,
    class_time TIME    NOT NULL,
    PRIMARY KEY (class_id, class_day, class_time)
);
```

`class_day` and `class_time` then move out of `class`. The current schema is
correct for one meeting per week; this is the first change worth making.

**Adding a teacher inline would break 3NF.** Putting `teacher_name` and
`teacher_phone` on `class` creates `id → teacher_name → teacher_phone`, a
transitive dependency, and the teacher's number would then be duplicated
across every class they teach. A `teacher` table with `class.teacher_id`
keeps 3NF. The same applies to subject and level if those become more than
free text.

A smaller one: if you add a fee, put a per-class price on `class` and a
per-student price on `student_class`. A class-level price stored in
`student_class` would depend on only half the key — a 2NF violation.
