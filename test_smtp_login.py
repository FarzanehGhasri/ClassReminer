"""
Isolated test: just tries to log in to Gmail's SMTP server, nothing else.
Run this first to confirm your App Password works before running the
full project. Delete this file once login succeeds.
"""
import smtplib

USERNAME = "farzanehghasri.alborz@gmail.com"  # must match exactly the account the App Password was made for
PASSWORD = "hxkoflzxuvfnkjvp"

# Diagnostic: catches hidden whitespace, wrong length, or accidental
# quote characters that copy-paste sometimes introduces.
print("Password length:", len(PASSWORD), "(should be exactly 16)")
print("Password repr:", repr(PASSWORD), "(check for stray spaces/quotes)")
print()

try:
    with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as smtp:
        smtp.starttls()
        smtp.login(USERNAME, PASSWORD)
    print("Login succeeded! Your credentials are correct.")
except smtplib.SMTPAuthenticationError as error:
    print("Login FAILED. Google rejected the credentials.")
    print("Details:", error)
    print("\nCheck: 2-Step Verification is ON, App Password is fresh, no spaces, username matches exactly.")