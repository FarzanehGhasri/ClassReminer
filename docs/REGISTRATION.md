# Registration form

A student-facing form that writes straight into the `student` table, so you
no longer add people by hand with `psql`.

```bash
docker compose up -d        # database + form + Adminer, all of it
```

The form is then on <http://localhost:8000>. That is the whole setup: the
`web` service in `docker-compose.yml` builds the image from the `Dockerfile`
and runs gunicorn, so nothing needs installing on the host.

### Running it without Docker

Useful while editing code, since a change takes effect on restart rather than
on rebuild:

```bash
pip install -r requirements.txt
python3 run_web.py          # http://127.0.0.1:8000
```

The database still has to be up (`docker compose up -d db`). This path uses
Flask's development server, which is single-threaded and not meant for real
traffic — the container runs gunicorn instead.

### After changing code

The image holds a copy of the source, so a rebuild is needed for the running
container to see edits:

```bash
docker compose up -d --build web
```

### Which host name to use

Inside the Docker network, containers reach each other by service name, so the
`web` container connects to `db`. On the host, the database is reached through
the published port on `localhost`. `.env` says `localhost` and the compose file
overrides it to `db` for that one container, so both paths work without you
editing anything.

| Running | `POSTGRES_HOST` |
| --- | --- |
| `web` container | `db` (set in `docker-compose.yml`) |
| `python3 run_web.py` on the host | `localhost` (from `.env`) |

### Health

`GET /healthz` returns `{"status": "ok"}` and is what the container's
healthcheck calls. It deliberately does not touch the database: if it did, a
brief database outage would mark the web container unhealthy and restart it,
which fixes nothing and drops in-flight requests. Postgres has its own
healthcheck, and `web` waits on it before starting.

## The fields

Every rule below is enforced three times: in the browser so the student sees
it immediately, on the server in `core/models/`, and in the database as a SQL
domain. The database is the authority; the other two exist to give a readable
Persian message instead of a failed insert.

| Field | Example | Accepted | Rejected |
| --- | --- | --- | --- |
| **نام** | `سارا` | Persian letters, with space, hyphen or ZWNJ between words. 1–60 characters. | `Sara`, `سارا۱`, `ساراSara`, blank, leading or trailing space |
| **نام خانوادگی** | `احمدی` | Same rule. `حسین‌زاده` (ZWNJ) and `آل-احمد` (hyphen) both pass. | `Ahmadi`, digits, mixed script |
| **شماره تماس** | `0912 345 6789` | Depends on the country picked — see below. Stored as `+989123456789`. | anything the chosen country's rule refuses |
| **ایمیل** | `sara@gmail.com` | One `@`, a domain with a dot, max 254 characters. | `sara@gmail`, `a..b@x.com`, `lkj;lj@gmail.com`, spaces |

### Why Persian-only names

The `persian_name` domain rejects Latin script outright. This is deliberate:
the reminder messages address students by name in Persian, and a mix of
scripts in one column makes sorting and addressing inconsistent. It also means
**neither of the existing CSVs imports** — every row there has a Latin name.

If you ever need to accept Latin names, that is a schema change
(`db/init/01_schema.sql`), not a form change. Loosening only the form would
produce an insert the database refuses.

## The phone field

The student picks a country first; the rule and the example update to match.
What they type is normalised before it is stored, so all of these are the
same number and all are accepted under 🇮🇷 ایران:

```
09122025452      0912-202-5452      ۰۹۱۲۲۰۲۵۴۵۲
9122025452       0912 202 5452      (0912) 202-5452
+989122025452    +98 912 202 5452   0098 912 202 5452
```

All of them are stored as `+989122025452`.

A number that does not fit the chosen country is refused rather than
reinterpreted: entering an Iranian number while 🇬🇧 بریتانیا is selected is an
error, not a silent switch to Iran. The student either fixes the number or
changes the country.

### Countries offered

Iran, Turkey, UAE, Iraq, UK, Germany, USA/Canada, Sweden, Netherlands,
France, Australia, Azerbaijan, Armenia, Georgia, Qatar, Oman, Kuwait,
Afghanistan.

Mobile numbers only. Landlines are rejected on purpose — a class reminder that
lands on a desk phone reaches nobody.

### Adding a country

One entry in `COUNTRIES` in `core/models/country.py`:

```python
Country("NO", "+47", "نروژ", "🇳🇴", r"[49]\d{7}", "",
        "412 34 567", "۸ رقم پس از کد کشور"),
```

That is the whole change. The picker, the live hint, the server validation and
the stored format all follow from it — no template edit, no JavaScript edit,
no SQL. `tests/test_registration.py::test_a_new_country_needs_no_code_change`
holds that guarantee in place.

The fields are: ISO code, dial code, Persian name, flag, the pattern the
*national* number must match (no trunk zero), the trunk prefix the country
uses (`"0"` or `""`), an example as a local would write it, and the rule in
Persian for the hint line.

## Duplicates

`phone_number` is unique, and `email` is unique case-insensitively. A student
registering twice gets a field-level message (`این شماره تماس قبلاً ثبت شده
است.`) rather than an error page, and no second row is created.

## What the form does not do

Known limits, all deliberate:

- **It creates a student, not an enrolment.** `student_class` stays empty until
  you assign the student to a class. The reminder job only reads enrolments, so
  a newly registered student receives nothing until you do that.
- **There is no rate limiting and no CAPTCHA.** Anyone who can reach the URL can
  create rows. Put it behind a reverse proxy with a rate limit, and TLS, before
  exposing it publicly — gunicorn is meant to run behind one, not directly on
  the open internet.
- **There is no authentication and no edit or delete.** Corrections are made in
  `psql`.
- **A phone number is validated for shape, not existence.** `+989120000000`
  passes every rule and may belong to nobody. Only sending to it proves
  otherwise.
- **No confirmation e-mail is sent**, so a typo in a valid-looking address is
  not caught at registration.

## How it is put together

```
web/app.py                 HTTP only — parses the request, returns JSON
  └─ core/registration.py  the use case, depends on an interface
       ├─ core/models/student.py   the entity and its invariants
       │    └─ core/models/phone_number.py ─ core/models/country.py
       └─ core/interfaces/student_repository.py   (abstract)
            └─ infrastructure/postgres_student_writer.py   the only SQL
```

`run_web.py` is the composition root: the one file that builds concrete classes
and wires them together, exactly as `main.py` does for the reminder job.

The seams that matter:

- **`StudentRepository` is separate from `RecipientRepository`.** Registration
  writes one student; the scheduler reads enrolments. Neither has any use for
  the other's method, so they are two small interfaces rather than one that
  forces either side to stub something out.
- **`RegistrationService` never imports psycopg.** It depends on the abstract
  repository, which is why `tests/test_registration.py` exercises the whole
  use case against an in-memory fake with no database running.
- **The country registry is the single source of the dialling rules.** The
  browser fetches it from `/api/countries` rather than keeping its own copy,
  so the two cannot drift apart.
- **`Student.create` is the only way to build a student.** The form and the CSV
  importer both go through it, so they cannot disagree about what is valid.
