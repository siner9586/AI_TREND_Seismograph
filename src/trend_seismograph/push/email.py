from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def push_email(subject: str, body: str, *, to_addr: str | None = None) -> dict:
    host = os.getenv("SMTP_HOST")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    recipient = to_addr or os.getenv("PUSH_EMAIL_TO") or user
    if not host or not user or not password or not recipient:
        return {"channel": "email", "skipped": True, "reason": "SMTP env not configured"}
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = user
    message["To"] = recipient
    message.set_content(body)
    with smtplib.SMTP_SSL(host, 465, timeout=20) as smtp:
        smtp.login(user, password)
        smtp.send_message(message)
    return {"channel": "email", "skipped": False, "ok": True}
