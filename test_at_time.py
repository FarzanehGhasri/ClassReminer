"""
For manual testing: lets you simulate "now" as any date/time you want,
so you can test different students/schedules without waiting for the
real clock or editing this file each time.

Usage:
    python test_at_time.py "2026-07-27 10:00"
    python test_at_time.py "2026-08-01 17:30"

If no argument is given, uses the current real time.
"""
import sys
from datetime import datetime

from main import build_scheduler
from utils.logger import setup_logging

setup_logging()

if len(sys.argv) > 1:
    fake_now = datetime.strptime(sys.argv[1], "%Y-%m-%d %H:%M")
else:
    fake_now = datetime.now()

print(f"Simulating run at: {fake_now.strftime('%A %Y-%m-%d %H:%M')}")

scheduler = build_scheduler()
scheduler.run(now=fake_now)

print("Done — check logs/app.log for what happened.")
