"""
Knows only how to send a raw email over SMTP. Doesn't know about
Recipients, templates, or class links — that's EmailChannel's job.
Separating these means either can change independently (e.g. swap SMTP
for an HTTP-based provider later without touching EmailChannel).
"""
import smtplib
from dataclasses import dataclass
from email.mime.text import MIMEText


@dataclass(frozen=True)
class SmtpCredentials:
    host: str
    port: int
    username: str
    password: str


class SmtpClient:
    def __init__(self, credentials: SmtpCredentials):
        self._credentials = credentials

    def send(self, to_address: str, subject: str, body: str) -> None:
        message = MIMEText(body)
        message["Subject"] = subject
        message["To"] = to_address
        raw_message = message.as_string()

        if self._credentials.port == 465:
            with smtplib.SMTP_SSL(self._credentials.host, self._credentials.port, timeout=15) as smtp:
                smtp.login(self._credentials.username, self._credentials.password)
                smtp.sendmail(self._credentials.username, [to_address], raw_message)
        else:
            # Port 587 (or others): plain connection upgraded via STARTTLS.
            # Some networks/firewalls block 465 but allow 587, or vice versa.
            with smtplib.SMTP(self._credentials.host, self._credentials.port, timeout=15) as smtp:
                smtp.starttls()
                smtp.login(self._credentials.username, self._credentials.password)
                smtp.sendmail(self._credentials.username, [to_address], raw_message)