"""
For manual testing: forces "now" to Monday 10:00 so you can confirm the
whole pipeline (load CSV -> check schedule -> send email -> log) works
without waiting for the real clock to hit 10:00.

Run: python3 test_run_now.py
Remove this file once you've confirmed everything works — it's just for
testing, not for production use (that's what main.py + cron is for).
"""
from datetime import datetime

from main import build_scheduler
from utils.logger import setup_logging

setup_logging()

fake_now = datetime(2026, 7, 27, 10, 0)  # a Monday, 10:02 AM — inside the 5-min window
print(f"Simulating run at: {fake_now.strftime('%A %Y-%m-%d %H:%M')}")

scheduler = build_scheduler()
scheduler.run(now=fake_now)

print("Done — check logs/app.log for what happened.")
