solid-email-automation/
│
├── README.md                                # setup guide + SOLID mapping explained
├── requirements.txt                         # requests, python-dotenv
├── .env.example                             # copy to .env, fill in secrets
├── .gitignore                               # excludes .env, logs, __pycache__, sent_log.db
│
├── core/
├──── __init__.py
├────| models/
│   ├── __init__.py          # re-exports Recipient, Schedule — public API unchanged
│   ├── recipient.py
│   └── schedule.py
|
├────| interfaces/
│   ├── __init__.py          # re-exports all five — public API unchanged
│   ├── notification_channel.py
│   ├── recipient_repository.py
│   ├── duplicate_guard.py
│   ├── template_renderer.py
│   └── failure_handler.py
└──── scheduler.py
│
├── channels/                                # NotificationChannel implementations (plug-ins)
│   ├── __init__.py
│   ├── email_channel.py                     # builds + sends email via SmtpClient + TemplateRenderer
│   ├── telegram_channel.py                  # sends via BotApiClient
│   └── bale_channel.py                      # sends via BotApiClient (Telegram-compatible API)
│
├── infrastructure/                          # concrete implementations of the other interfaces
│   ├── __init__.py
│   ├── csv_recipient_repository.py          # RecipientRepository → reads data/students.csv
│   ├── sqlite_duplicate_guard.py            # DuplicateGuard → reads/writes data/sent_log.db
│   ├── file_template_renderer.py            # TemplateRenderer → reads templates/*.txt
│   ├── smtp_client.py                       # raw SMTP transport (used by EmailChannel)
│   ├── bot_api_client.py                    # raw bot-API HTTP calls (used by Telegram/Bale)
│   └── email_admin_alerter.py               # FailureHandler → emails you when a send fails
│
├── utils/                                   # small, dependency-free helpers
│   ├── __init__.py
│   ├── logger.py                            # configures logging to logs/app.log + console
│   ├── validator.py                         # email format / chat-ID / CSV row validation
│   └── retry.py                             # retry decorator for flaky network calls
│
├── config/
│   ├── __init__.py
│   └── settings.py                          # all config, reads from .env
│
├── data/
│   ├── students.csv                         # recipient list + per-recipient schedule
│   └── sent_log.db                          # (created at runtime) duplicate-send guard
│
├── logs/
│   ├── .gitkeep
│   └── app.log                              # (created at runtime) full run history
│
├── templates/
│   ├── subject.txt                          # editable email subject — {name} {class_link} {date}
│   └── body.txt                             # editable email body — same placeholders
│
├── deploy/
│   ├── solid-email-automation.service       # systemd unit (alternative to cron)
│   └── solid-email-automation.timer         # runs every 5 minutes
│
└── main.py                                  # ★ COMPOSITION ROOT — only file that imports
                                              #   concrete classes and wires them to interfaces



A SOLID-structured notification engine. core/ is a reusable framework — copy it into a future project unchanged and just write new infrastructure/ and channels/ implementations for whatever's different.

Single Responsibility — each class has one reason to change: ScheduleChecker only decides timing, Scheduler only orchestrates, SmtpClient only knows SMTP, EmailChannel only knows how to build a class-notification email (and delegates sending/rendering to injected collaborators).

Open/Closed — add a new channel (WhatsApp, SMS, Slack) by writing a new class that implements NotificationChannel. Add a new data source (Google Sheets, a database) by implementing RecipientRepository. core/scheduler.py never changes for either.

Liskov Substitution — anywhere a NotificationChannel or RecipientRepository is used, any implementation works interchangeably; Scheduler doesn't know or care which one it got.

Interface Segregation — each interface in core/interfaces.py is small and does one job; implementers never have to stub out methods they don't need.

Dependency Inversion — core/scheduler.py (high-level policy) depends only on core/interfaces.py (abstractions), never on infrastructure/ or channels/ (low-level detail) directly. main.py is the single seam where concrete classes meet abstractions.

Reusing this for a future project
Copy core/ and utils/ unchanged.
Write new infrastructure//channels/ classes only for what's actually different (e.g. PostgresRecipientRepository, SlackChannel).
Rewire main.py's build_scheduler() with the new pieces.
Setup
bash
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # fill in credentials
python3 main.py
Schedule it
*/5 * * * * cd /opt/solid-email-automation && /usr/bin/python3 main.py

or use deploy/*.service + deploy/*.timer with systemd.

Before selling this to a customer

Confirm your hosting, SMTP, and payment providers' terms allow serving Iran-based customers — this varies by provider and changes over time.