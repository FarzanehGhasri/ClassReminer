"""
Registration flow for the Bale bot:

1. Any message from a student with no active session shows exactly one
   button: "ورود به آکادمی زبان Masi". Free text is ignored until this
   button is tapped - the bot just re-shows the button.
2. Tapping the button -> bot asks (in Persian) for their phone number.
3. The phone number is validated (11 digits, must start with 09).
4. The phone number is looked up in data/students.csv:
   - found  -> the bot replies with the student's name, phone number,
               email, schedule_weekday and schedule_time, plus a menu of
               5 buttons: ویرایش اطلاعات، تماس با ما، ورود به سایت،
               کانال بله، کانال تلگرام
               (contact-us is a placeholder for now - behavior to be
               specified later; site/Bale-channel/Telegram-channel link
               out to the URLs in SITE_URL / BALE_CHANNEL_URL /
               TELEGRAM_CHANNEL_URL below, which need to be filled in
               with the real links).

               ویرایش اطلاعات ("edit info") opens a field picker
               (نام / شماره / ایمیل) as buttons. Tapping one of them shows
               the value currently on file for that field, then asks for
               the new value ("لطفا نام/شماره تماس/ایمیل جدید خود را وارد
               کنید"). The typed value is validated with the same rules
               as registration; if it matches the same field already
               stored for a *different* student, the bot rejects it
               ("این نام/شماره/ایمیل قبلا برای دانش‌آموز دیگری ثبت شده
               است...") and asks for a different value. Otherwise a
               preview of the updated record is shown together with
               بله/خیر buttons. Only "بله" writes the change back to
               data/students.csv; "خیر" (or closing the confirm step
               without answering) discards it. "بازگشت به منوی اصلی" is
               available as a button at every step of this sub-flow
               (field picker, value prompt, and confirmation) and returns
               to the main menu without saving anything.
   - not found -> the bot asks (in Persian) for name, then email, both
               validated, and appends a new row to
               data/new_registrations.csv (students.csv is left untouched
               in this path - only confirmed edits above ever modify it).
               A "بازگشت به منوی اصلی" button is offered on the name and
               email prompts (i.e. once a phone number has been entered),
               so the person can bail out of registration at that point.

Restarting: whenever the conversation needs to reset to square one (the
person taps "بازگشت به منوی اصلی" with no phone on record yet, or their
phone number no longer matches a row in students.csv), the bot shows the
welcome greeting and then immediately asks for the phone number again -
no extra button tap needed in between. That phone-number prompt itself
has no back button, since it's the first step of the flow and there's
nowhere further back to go.

Design note: the bot is split into small, single-purpose collaborators
(SOLID's SRP in particular) so each piece can change independently:
  - BaleClient            talks to the Bale HTTP API only.
  - StudentRepository     is the only thing that reads/writes students.csv.
  - NewRegistrationRepository  is the only thing that writes new_registrations.csv.
  - Keyboards             builds reply/inline keyboards only.
  - ConversationStateStore   holds per-chat conversation state only.
  - RegistrationBot       wires the above together and holds the flow logic.

Run: python register_bale_students.py
Leave it running while students register; stop with Ctrl+C.
"""
import csv
import os
import re
import time

import requests

from config import settings

SITE_URL = "https://masiacademy.ir"
BALE_CHANNEL_URL = "https://ble.ir/join/4kFFZMoLdZ"
TELEGRAM_CHANNEL_URL = "https://t.me/REPLACE_ME"

STUDENTS_CSV_PATH = settings.RECIPIENTS_CSV_PATH
NEW_REGISTRATIONS_CSV_PATH = os.path.join(os.path.dirname(STUDENTS_CSV_PATH), "new_registrations.csv")
API_BASE = settings.BALE_API_BASE
BOT_TOKEN = settings.BALE_BOT_TOKEN

ENTRY_BUTTON_LABEL = "ورود به آکادمی زبان Masi"
BACK_TO_MAIN_LABEL = "بازگشت"


NAME_PATTERN_ENGLISH = re.compile(r"^[A-Za-z\s]+$")
NAME_PATTERN_PERSIAN = re.compile(r"^[\u0600-\u06FF\s]+$")
PHONE_PATTERN = re.compile(r"^09\d{9}$")
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Persian and Arabic-Indic digits -> ASCII digits, so phone numbers typed on a
# Persian keyboard (۰۹۱۲...) are treated the same as ASCII ones (09123...).
_DIGIT_TRANSLATION = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "0123456789" * 2)


def to_ascii_digits(text: str) -> str:
    return (text or "").translate(_DIGIT_TRANSLATION)


def normalize_phone(phone: str) -> str:
    """
    Digits only, Persian/Arabic-Indic converted to ASCII, and reduced to the
    last 10 digits. This lets a stored number that lost its leading zero in
    Excel (e.g. "9123456789") still match a typed "09123456789".
    """
    digits = re.sub(r"\D", "", to_ascii_digits(phone))
    return digits[-10:] if len(digits) >= 10 else digits

def normalize_contact_phone(phone: str) -> str:
    """
    Converts phone numbers received from Bale contacts
    from international format (989122176748)
    to local format (09122176748).
    """
    phone = re.sub(r"\D", "", to_ascii_digits(phone))

    if phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]

    return phone

def is_valid_name(name: str) -> bool:
    name = name.strip()
    return bool(name) and bool(NAME_PATTERN_ENGLISH.match(name) or NAME_PATTERN_PERSIAN.match(name))


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_PATTERN.match(to_ascii_digits(phone.strip())))


def is_valid_email(email: str) -> bool:
    return bool(EMAIL_PATTERN.match(email.strip()))


# Editable fields for the "ویرایش اطلاعات" sub-flow: the internal key used in
# conversation state/callback_data, the CSV column it maps to, the validator
# reused from registration, and the prompt shown when asking for a new value.
EDITABLE_FIELDS = {
    "name": {
        "label": "نام",
        "column": "name",
        "validator": is_valid_name,
        "prompt": "لطفا نام جدید خود را وارد کنید.",
        "invalid_message": "لطفا یک نام معتبر با حروف فارسی یا انگلیسی وارد کنید.",
    },
    
    "email": {
        "label": "ایمیل",
        "column": "email",
        "validator": is_valid_email,
        "prompt": "لطفا ایمیل جدید خود را وارد کنید.",
        "invalid_message": "ایمیل نامعتبر است. لطفا دوباره وارد کنید.",
    },
}


class StudentRepository:
    """The only object that reads or writes data/students.csv."""

    def __init__(self, csv_path):
        self.csv_path = csv_path

    def _read_all(self):
        # utf-8-sig (not utf-8) because a CSV saved from Excel often has a
        # BOM at the very start of the file; reading it as plain utf-8 would
        # leave that BOM stuck to the first column's header (e.g.
        # "\ufeffphone_number"), which silently breaks every lookup.
        with open(self.csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)
        return fieldnames, rows

    def load_all(self):
        _, rows = self._read_all()
        return rows

    def find_by_phone(self, phone):
        target = normalize_phone(phone)
        if not target:
            return None
        for row in self.load_all():
            if normalize_phone(row.get("phone_number", "")) == target:
                return row
        return None

    def update_field(self, phone, column, new_value):
        """
        Overwrites a single column for the row matching phone, then rewrites
        the whole file (csv has no in-place row update). Returns the updated
        row, or None if no row matched.
        """
        fieldnames, rows = self._read_all()
        target = normalize_phone(phone)
        updated_row = None
        for row in rows:
            if normalize_phone(row.get("phone_number", "")) == target:
                row[column] = new_value
                updated_row = row
                break

        if updated_row is None:
            return None

        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return updated_row

    def find_duplicate(self, column, value, exclude_phone):
        """
        Returns the row (if any) where `column` already equals `value`,
        ignoring the record identified by exclude_phone (the student's own
        current row, so editing a field to the same value it already had -
        or editing a different field - never counts as a duplicate).
        Phone comparisons are normalized; name/email comparisons are
        case-insensitive/whitespace-trimmed.
        """
        exclude_target = normalize_phone(exclude_phone)
        for row in self.load_all():
            if normalize_phone(row.get("phone_number", "")) == exclude_target:
                continue
            if column == "phone_number":
                if normalize_phone(row.get(column, "")) == normalize_phone(value):
                    return row
            else:
                if (row.get(column) or "").strip().lower() == (value or "").strip().lower():
                    return row
        return None


class NewRegistrationRepository:
    """The only object that writes data/new_registrations.csv."""

    FIELDNAMES = ["name", "phone_number", "email", "bale_chat_id"]

    def __init__(self, csv_path):
        self.csv_path = csv_path

    def append(self, name, phone, email, chat_id):
        file_exists = os.path.exists(self.csv_path)

        if not file_exists:
            # utf-8-sig adds a BOM, which Excel needs to display Persian
            # text correctly. It must only be written once, right at the
            # start of the file - so this happens only on the very first
            # registration.
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
                writer.writeheader()

        # Every append after that uses plain utf-8 (declaring utf-8-sig here
        # would re-add a BOM) since the file already starts with one.
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.FIELDNAMES)
            writer.writerow({"name": name, "phone_number": phone, "email": email, "bale_chat_id": chat_id})

    def load_all(self):
        if not os.path.exists(self.csv_path):
            return []

        with open(self.csv_path, newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))


    def find_by_phone(self, phone):
        target = normalize_phone(phone)

        for row in self.load_all():
            if normalize_phone(row.get("phone_number", "")) == target:
                return row

    def update_field(self, phone, column, new_value):
        fieldnames = self.FIELDNAMES
        rows = self.load_all()

        updated = None

        for row in rows:
            if normalize_phone(row["phone_number"]) == normalize_phone(phone):
                row[column] = new_value
                updated = row
                break

        if updated is None:
            return None

        with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        return updated


    def find_duplicate(self, column, value, exclude_phone):
        for row in self.load_all():

            if normalize_phone(row["phone_number"]) == normalize_phone(exclude_phone):
                continue

            if (row.get(column, "").strip().lower()
                    == value.strip().lower()):
                return row

        return None

        

    
class BaleClient:
    """The only object that talks to the Bale HTTP API."""

    def __init__(self, api_base, bot_token):
        self.api_base = api_base
        self.bot_token = bot_token

    def _url(self, method):
        return f"{self.api_base}/bot{self.bot_token}/{method}"

    def send_message(self, chat_id, text, reply_markup=None):
        payload = {"chat_id": chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        requests.post(self._url("sendMessage"), json=payload, timeout=15)

    def answer_callback_query(self, callback_query_id, text=None):
        payload = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        requests.post(self._url("answerCallbackQuery"), json=payload, timeout=15)

    def remove_keyboard(self, chat_id, text):
        self.send_message(chat_id, text, {"remove_keyboard": True})

    def get_updates(self, offset=None, timeout=30):
        params = {"timeout": timeout}
        if offset is not None:
            params["offset"] = offset
        response = requests.get(self._url("getUpdates"), params=params, timeout=timeout + 10)
        response.raise_for_status()
        return response.json().get("result", [])


class Keyboards:
    """Builds every reply/inline keyboard. No other object constructs one."""

    @staticmethod
    def entry():
        return {
            "keyboard": [
                [
                    {
                        "text": "📱 ارسال شماره من",
                        "request_contact": True,
                    }
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }


    @staticmethod
    def restart_only():
        return {
            "keyboard": [
                [
                    {
                        "text": "شروع مجدد"
                    }
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }

    @staticmethod
    def request_phone():
        return {
            "keyboard": [
                [
                    {
                        "text": "📱 ارسال شماره من",
                        "request_contact": True,
                    }
                ],
                [
                    {
                        "text": "شروع مجدد"
                    }
                ]
            ],
            "resize_keyboard": True,
            "one_time_keyboard": False,
        }


    @staticmethod
    def main_menu():
        return {
            "inline_keyboard": [
                [
                    {"text": "✏️ ویرایش اطلاعات ", "callback_data": "edit_info"},
                    {"text": "📞 تماس با ما", "callback_data": "contact_us"},
                ],
                [{"text": "🌐 ورود به سایت", "url": SITE_URL}],
                [
                    {"text": "💬 کانال بله", "url": BALE_CHANNEL_URL},
                    {"text": "📢 کانال تلگرام ", "url": TELEGRAM_CHANNEL_URL},
                ],
            ]
        }

    @staticmethod
    def edit_field_picker():
        return {
            "inline_keyboard": [
                [{"text": field_def["label"], "callback_data": f"edit_field:{key}"}]
                for key, field_def in EDITABLE_FIELDS.items()
            ]
            + [[{"text": BACK_TO_MAIN_LABEL, "callback_data": "back_to_main"}]]
        }

    @staticmethod
    def back_only():
        return {"inline_keyboard": [[{"text": BACK_TO_MAIN_LABEL, "callback_data": "back_to_main"}]]}

    @staticmethod
    def confirm():
        return {
            "inline_keyboard": [
                [
                    {"text": "بله", "callback_data": "confirm_edit_yes"},
                    {"text": "خیر", "callback_data": "confirm_edit_no"},
                ],
                [{"text": BACK_TO_MAIN_LABEL, "callback_data": "back_to_main"}],
            ]
        }


class ConversationStateStore:
    """Holds per-chat conversation state only. No flow logic lives here."""

    def __init__(self):
        self._states = {}

    def get(self, chat_id):
        return self._states.get(chat_id)

    def set(self, chat_id, state):
        self._states[chat_id] = state

    def clear(self, chat_id):
        self._states.pop(chat_id, None)


class RegistrationBot:
    """Wires the collaborators above together and holds the conversation flow."""

    def __init__(self, client, students_repo, new_registrations_repo, state_store):
        self.client = client
        self.students_repo = students_repo
        self.new_registrations_repo = new_registrations_repo
        self.state_store = state_store

    # ---- formatting helpers ----

    @staticmethod
    def format_record(row):
        class_day = row.get("schedule_weekday") or "---"
        class_time = row.get("schedule_time") or "---"

        return (
            f"نام: {row.get('name', '')}\n"
            f"شماره تماس: {row.get('phone_number', '')}\n"
            f"ایمیل: {row.get('email', '')}\n"
            f"روز کلاس: {class_day}\n"
            f"ساعت کلاس: {class_time}"
        )
    def format_student_info(self, row):
        name = row.get("name", "").strip()

        return (
            f"سلام {name} عزیز! 🌸\n"
            f"به آکادمی زبان Masi خوش آمدید.\n\n"
            + self.format_record(row)
        )

    def build_edit_preview(self, phone, column, new_value):
        student = (
            self.students_repo.find_by_phone(phone)
            or self.new_registrations_repo.find_by_phone(phone)
        )

        if student is None:
            return "خطا در یافتن اطلاعات."

        preview = student.copy()
        preview[column] = new_value

        return (
            "آیا اطلاعات جدید زیر صحیح است؟\n\n"
            + self.format_record(preview)
        )

    def show_main_menu(self, chat_id, phone):
        student = (
        self.students_repo.find_by_phone(phone)
        or self.new_registrations_repo.find_by_phone(phone)
    )
        if not student:
            self.start_over(chat_id)
            return
        self.state_store.set(chat_id, {"step": "menu", "phone": student.get("phone_number", "")})
        self.client.send_message(chat_id,"",Keyboards.restart_only())
        self.client.send_message(chat_id,self.format_student_info(student), Keyboards.main_menu())

    def show_welcome(self, chat_id):
        self.state_store.clear(chat_id)

        self.client.send_message(
            chat_id,
            "به آکادمی زبان Masi خوش آمدید!",
            Keyboards.entry()
        )


    def start_over(self, chat_id):
        """
        Resets the conversation: shows the welcome greeting, then goes
        straight into asking for the phone number (no button tap needed
        in between). No back button is offered at this step - the phone
        prompt is the very first thing in the flow, so there's nowhere
        further back to go.
        """
        self.client.send_message(chat_id, "به آکادمی زبان Masi خوش آمدید!")
        self.client.send_message(
                chat_id,
                "به آکادمی زبان Masi خوش آمدید!\n\n"
                "برای ادامه، شماره تلفن خود را با استفاده از دکمه زیر ارسال کنید.",
                Keyboards.request_phone(),
        )
        return

    # ---- message (free text) handling ----

    def request_phone(self, chat_id):
        self.state_store.set(chat_id, {"step": "awaiting_phone"})

        self.client.send_message(
            chat_id,
            "برای ادامه، شماره تلفن خود را با استفاده از دکمه زیر ارسال کنید.",
            Keyboards.request_phone()
        )


    def handle_message(self, message):
        
        chat_id = message["chat"]["id"]

        contact = message.get("contact")

        if contact:
            text = normalize_contact_phone(contact["phone_number"])
            self.client.send_message(
            chat_id,
            "شماره شما دریافت شد.",
            Keyboards.restart_only()
        )

            # If the user shares a contact, treat it as the phone step.
            if self.state_store.get(chat_id) is None:
                self.state_store.set(chat_id, {"step": "awaiting_phone"})
        else:
            text = (message.get("text") or "").strip()

        if text == "شروع مجدد":
            self.show_welcome(chat_id)
            return
        # Restart the conversation whenever the user sends /start
        if text == "/start":
            self.show_welcome(chat_id)
            return

        state = self.state_store.get(chat_id)

        if state is None:
            self.show_welcome(chat_id)
            return

        step = state["step"]

        if step == "awaiting_phone":
            if not is_valid_phone(text):
                self.client.send_message(
                    chat_id,
                    "شماره تلفن نامعتبر است. لطفا یک شماره ۱۱ رقمی که با ۰۹ شروع می‌شود وارد کنید.",
                )
                return

            student = self.students_repo.find_by_phone(text)
            if student is None:
                student = self.new_registrations_repo.find_by_phone(text)

            if student:
                self.state_store.set(
                    chat_id,
                    {
                        "step": "menu",
                        "phone": student["phone_number"],
                    },
                )

                self.client.send_message(chat_id, "", Keyboards.restart_only())
                self.client.send_message(
                    chat_id,
                    self.format_student_info(student),
                    Keyboards.main_menu(),
                )
                return

                

            state["phone"] = to_ascii_digits(text.strip())
            state["step"] = "awaiting_name"
            self.client.send_message(
                chat_id,
                "خوشحالیم که آکادمی زبان Masi را انتخاب کرده‌اید! 🌸\n\n"
                "لطفا نام و نام خانودگی خود را وارد فرمایید.\n"
                "شماره شما در سیستم ثبت نشده است.",
                Keyboards.back_only(),
            )
            return

        if step == "awaiting_name":
            if not is_valid_name(text):
                self.client.send_message(
                    chat_id,
                    "لطفا یک نام معتبر با حروف فارسی یا انگلیسی وارد کنید.",
                    Keyboards.back_only(),
                )
                return
            state["name"] = text
            state["step"] = "awaiting_email"

            self.client.send_message(
                chat_id,
                f"{text} عزیز، خوش آمدید! 🌸\n\nلطفا ایمیل خود را وارد کنید.",
                Keyboards.back_only(),
            )

        if step == "awaiting_email":
            if not is_valid_email(text):
                self.client.send_message(
                    chat_id,
                    "ایمیل نامعتبر است. لطفا دوباره وارد کنید.",
                    Keyboards.back_only(),
                )
                return

            self.new_registrations_repo.append(
                state["name"],
                state["phone"],
                text,
                chat_id,
            )

            self.client.send_message(
                chat_id,
                f"تبریک {state['name']} عزیز! 🎉\n\n"
                "ثبت‌نام شما با موفقیت انجام شد.\n"
                "از این پس اخبار و اطلاعیه‌های آکادمی زبان Masi را از طریق این ربات دریافت خواهید کرد."
            )

            new_student = {
                "name": state["name"],
                "phone_number": state["phone"],
                "email": text,
                "schedule_weekday": "",
                "schedule_time": "",
            }

            self.state_store.set(
                chat_id,
                {
                    "step": "menu",
                    "phone": state["phone"],
                },
            )

            self.client.send_message(
                chat_id,
                self.format_student_info(new_student),
                Keyboards.main_menu(),
            )

            return

        if step == "menu":
            # A menu is showing and buttons are how you act on it - re-show
            # it rather than trying to interpret free text.
            self.show_main_menu(chat_id, state.get("phone"))
            return

        if step == "editing_select_field":
            # Field choice is button-only - re-show the picker.
            self.client.send_message(chat_id, "لطفا یکی از فیلدهای زیر را انتخاب کنید.", Keyboards.edit_field_picker())
            return


        if step == "editing_awaiting_value":
            field_key = state["edit_field"]
            field_def = EDITABLE_FIELDS[field_key]
            if not field_def["validator"](text):
                self.client.send_message(chat_id, field_def["invalid_message"], Keyboards.back_only())
                return

            new_value = to_ascii_digits(text.strip()) if field_key == "phone" else text.strip()

            duplicate = (
                self.students_repo.find_duplicate(
                    field_def["column"],
                    new_value,
                    state["phone"],
                )
                or
                self.new_registrations_repo.find_duplicate(
                    field_def["column"],
                    new_value,
                    state["phone"],
                )
            )

            if duplicate is not None:
                self.client.send_message(
                    chat_id,
                    f"این {field_def['label']} قبلا برای دانش‌آموز دیگری ثبت شده است. لطفا {field_def['label']} جدیدی وارد کنید.",
                    Keyboards.back_only(),
                )
                return

            state["new_value"] = new_value
            state["step"] = "editing_confirm"
            self.client.send_message(chat_id, self.build_edit_preview(state["phone"], field_def["column"], new_value), Keyboards.confirm())
            return

        if step == "editing_confirm":
            # Confirmation is button-only (بله/خیر) - re-show the prompt.
            field_def = EDITABLE_FIELDS[state["edit_field"]]
            self.client.send_message(chat_id, self.build_edit_preview(state["phone"], field_def["column"], state["new_value"]), Keyboards.confirm())
            return

    # ---- callback query (button tap) handling ----

    def handle_callback_query(self, callback_query):
        chat_id = callback_query["message"]["chat"]["id"]
        data = callback_query.get("data")
        state = self.state_store.get(chat_id)
        self.client.answer_callback_query(callback_query["id"])

        if data == "back_to_main":
            phone = state.get("phone") if state else None
            if not phone:
                self.start_over(chat_id)
                return
            self.show_main_menu(chat_id, phone)
            return

        if data == "edit_info":
            if not state or "phone" not in state:
                return
            self.state_store.set(chat_id, {"step": "editing_select_field", "phone": state["phone"]})
            self.client.send_message(chat_id, "کدام مورد را می‌خواهید ویرایش کنید؟", Keyboards.edit_field_picker())
            return

        if data == "contact_us":
            # Placeholder - real behavior to be defined later.
            self.client.send_message(
                chat_id,
                "📞 تماس با ما\n\n"
                "در صورت نیاز به راهنمایی یا پشتیبانی، می‌توانید با شماره زیر تماس بگیرید:\n\n"
                "📱 09122201562",
                Keyboards.main_menu(),
            )
            return

        if data and data.startswith("edit_field:"):
            field_key = data.split(":", 1)[1]
            field_def = EDITABLE_FIELDS.get(field_key)
            if not field_def or not state or "phone" not in state:
                return
            self.state_store.set(chat_id, {"step": "editing_awaiting_value", "phone": state["phone"], "edit_field": field_key})

            student = (
                self.students_repo.find_by_phone(state["phone"])
                or self.new_registrations_repo.find_by_phone(state["phone"])
            )

            current_value = student.get(field_def["column"], "") if student else ""


            prompt = f"مقدار فعلی {field_def['label']}: {current_value}\n\n{field_def['prompt']}"
            self.client.send_message(chat_id, prompt, Keyboards.back_only())
            return

        if data == "confirm_edit_yes":
            if not state or state.get("step") != "editing_confirm":
                return
            field_def = EDITABLE_FIELDS[state["edit_field"]]

            updated = self.students_repo.update_field(
                state["phone"],
                field_def["column"],
                state["new_value"],
            )

            if updated is None:
                updated = self.new_registrations_repo.update_field(
                    state["phone"],
                    field_def["column"],
                    state["new_value"],
                )

            if updated is None:
                self.client.send_message(
                    chat_id,
                    "خطا در بروزرسانی اطلاعات."
                )
                return
            
            self.state_store.set(chat_id, {"step": "menu", "phone": updated.get("phone_number", "")})
            self.client.send_message(
                chat_id,
                "",
                Keyboards.restart_only()
            )

            self.client.send_message(
                chat_id,
                "اطلاعات شما با موفقیت به‌روزرسانی شد.\n\n"
                + self.format_record(updated),
                Keyboards.main_menu()
            )
            return

        if data == "confirm_edit_no":
            phone = state.get("phone") if state else None
            if phone:
                self.show_main_menu(chat_id, phone)
            return

    def handle_update(self, update):
        if "message" in update:
            self.handle_message(update["message"])
        elif "callback_query" in update:
            self.handle_callback_query(update["callback_query"])

    def run(self):
        print("Listening for registrations. Press Ctrl+C to stop.")
        offset = None
        while True:
            updates = self.client.get_updates(offset=offset)

            for update in updates:
                self.handle_update(update)
                offset = update["update_id"] + 1

            if not updates:
                time.sleep(1)


def main():
    bot = RegistrationBot(
        client=BaleClient(API_BASE, BOT_TOKEN),
        students_repo=StudentRepository(STUDENTS_CSV_PATH),
        new_registrations_repo=NewRegistrationRepository(NEW_REGISTRATIONS_CSV_PATH),
        state_store=ConversationStateStore(),
    )
    bot.run()


if __name__ == "__main__":
    main()