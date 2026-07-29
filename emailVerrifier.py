import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

gmail_user = "farzanehghasri.alborz@gmail.com"
app_password = "hxkoflzxuvfnkjvp"


msg = MIMEMultipart()
msg["From"] = gmail_user
msg["To"] = "farzanehghasri.alborz@gmail.com"
msg["Subject"] = "Test from Python"

body = "سلام، این یک ایمیل تستی از پایتون است."
msg.attach(MIMEText(body, "plain", "utf-8"))

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login(gmail_user, app_password)
    server.send_message(msg)

print("Email sent successfully")

SMTP_USERNAME="farzanehghasri.alborz@gmail.com"
SMTP_PASSWORD="hxkoflzxuvfnkjvp"
