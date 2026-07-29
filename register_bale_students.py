"""
Conversational registration flow for the Bale bot.

Flow:
1. Student taps "Start" (sends /start, or any first message) -> bot asks for name.
2. Student types name          -> bot asks for phone number.
3. Student types phone number  -> validated (11 digits, must start with 09) -> bot asks for email.
4. Student types email address -> validated with a regex -> registration is processed:

   Matching is done against data/students.csv by phone number ONLY.
   students.csv is NEVER written to - all results go into data/new_students.csv.

     - phone found in students.csv AND email already known for that phone
           -> registration is skipped ("you're already registered")
     - phone found in students.csv but email is different
           -> the new email is added alongside the old one (semicolon separated),
              and a row is written/updated in data/new_students.csv
     - phone not found in students.csv at all
           -> a brand new row is written to data/new_students.csv

   data/new_students.csv is also checked on each registration so that a student
   registering more than once doesn't create duplicate rows there - repeat
   registrations with a new email simply get merged into their existing row.

Run: python register_bale_students.py
Leave it running while students register; stop with Ctrl+C.

Conversation state is kept in memory (per chat_id) while this script runs.
If you restart the script mid-conversation, a student just needs to send
another message to start over - nothing is lost on their end.
"""
import csv
import os
import re
import time

import requests

from config import settings

CSV_PATH = settings.RECIPIENTS_CSV_PATH  # data/students.csv - read-only, never modified
NEW_CSV_PATH = getattr(settings, "NEW_STUDENTS_CSV_PATH", None) or os.path.join(
    os.path.dirname(CSV_PATH) or ".", "new_students.csv"
)
API_BASE = settings.BALE_API_BASE
BOT_TOKEN = settings.BALE_BOT_TOKEN

NEW_CSV_FIELDS = ["name", "phone_number", "email", "bale_chat_id"]

# Exactly 11 digits, must start with "09" (e.g. 09123456789)
PHONE_RE = re.compile(r"^09\d{9}$")
# Simple, permissive email pattern: something@something.something
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# chat_id -> {"step": "awaiting_name" | "awaiting_phone" | "awaiting_email", "name": ..., "phone": ...}
conversation_state = {}


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-10:] if len(digits) >= 10 else digits


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.fullmatch((phone or "").strip()))


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_RE.fullmatch((email or "").strip()))


def load_students():
    """Read-only load of the master student list. This file is never written to."""
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_new_rows():
    if not os.path.exists(NEW_CSV_PATH):
        return []
    with open(NEW_CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def save_new_rows(rows):
    with open(NEW_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=NEW_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def send_message(chat_id, text):
    requests.post(
        f"{API_BASE}/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": text},
        timeout=15,
    )


def register_student(name, phone, email, chat_id):
    """
    Applies the matching rules described at the top of the file.
    Returns (status, display_name) where status is one of:
    "duplicate", "updated", "new"
    """
    target = normalize_phone(phone)

    # 1. Look up the phone number in the master list (read-only, never modified).
    master_match = None
    for row in load_students():
        if normalize_phone(row.get("phone_number", "")) == target:
            master_match = row
            break

    new_rows = load_new_rows()

    # 2. Also look it up in the new CSV, so re-registrations merge instead of duplicating.
    existing_new_row = None
    for row in new_rows:
        if normalize_phone(row.get("phone_number", "")) == target:
            existing_new_row = row
            break

    display_name = (master_match or {}).get("name") or (existing_new_row or {}).get("name") or name

    known_emails = set()
    if master_match and master_match.get("email"):
        known_emails.update(e.strip().lower() for e in master_match["email"].split(";") if e.strip())
    if existing_new_row and existing_new_row.get("email"):
        known_emails.update(e.strip().lower() for e in existing_new_row["email"].split(";") if e.strip())

    if not master_match and not existing_new_row:
        # Phone number seen nowhere before -> brand new row, students.csv untouched.
        new_rows.append({
            "name": name,
            "phone_number": phone,
            "email": email,
            "bale_chat_id": str(chat_id),
        })
        save_new_rows(new_rows)
        return "new", name

    if email.strip().lower() in known_emails:
        # Same phone + same email already registered -> nothing to do.
        return "duplicate", display_name

    # Same phone, new email -> merge the new email in with the known ones.
    combined_email = ";".join(sorted(known_emails | {email.strip().lower()}))
    if existing_new_row:
        existing_new_row["email"] = combined_email
        existing_new_row["bale_chat_id"] = str(chat_id)
        existing_new_row["name"] = display_name
    else:
        new_rows.append({
            "name": display_name,
            "phone_number": phone,
            "email": combined_email,
            "bale_chat_id": str(chat_id),
        })
    save_new_rows(new_rows)
    return "updated", display_name


def handle_message(message):
    chat_id = message["chat"]["id"]
    text = (message.get("text") or "").strip()
    state = conversation_state.get(chat_id)

    if state and state["step"] == "awaiting_name":
        if not text:
            send_message(chat_id, "Please type your full name.")
            return
        state["name"] = text
        state["step"] = "awaiting_phone"
        send_message(chat_id, f"Thanks {text}! Now please enter your phone number (e.g. 09123456789).")
        return

    if state and state["step"] == "awaiting_phone":
        if not is_valid_phone(text):
            send_message(
                chat_id,
                "That doesn't look like a valid phone number. It must be 11 digits "
                "and start with 09 (e.g. 09123456789). Please try again.",
            )
            return
        state["phone"] = text
        state["step"] = "awaiting_email"
        send_message(chat_id, "Great, now please enter your email address.")
        return

    if state and state["step"] == "awaiting_email":
        if not is_valid_email(text):
            send_message(chat_id, "That doesn't look like a valid email address. Please try again.")
            return

        status, display_name = register_student(state["name"], state["phone"], text, chat_id)
        if status == "duplicate":
            send_message(chat_id, f"You're already registered, {display_name} - nothing to do!")
        elif status == "updated":
            send_message(
                chat_id,
                f"Thanks {display_name}! We've added this new email address to your existing registration.",
            )
        else:
            send_message(chat_id, f"You're registered, {display_name}! Welcome aboard.")

        conversation_state.pop(chat_id, None)
        return

    # No active conversation (e.g. student just tapped "Start") -> begin the flow.
    conversation_state[chat_id] = {"step": "awaiting_name"}
    send_message(chat_id, "Welcome! Let's get you registered. What's your full name?")


def handle_update(update):
    if "message" in update:
        handle_message(update["message"])
    # Callback-query updates (the old "Register" button) are no longer used
    # since the flow now starts directly from the student's first message.


def main():
    print("Listening for student registrations. Press Ctrl+C to stop.")
    offset = None
    while True:
        params = {"timeout": 30}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(f"{API_BASE}/bot{BOT_TOKEN}/getUpdates", params=params, timeout=40)
        response.raise_for_status()
        updates = response.json().get("result", [])

        for update in updates:
            handle_update(update)
            offset = update["update_id"] + 1

        if not updates:
            time.sleep(1)


if __name__ == "__main__":
    main()