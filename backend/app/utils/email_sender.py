import os
import smtplib
from email.message import EmailMessage
from typing import List, Optional


def send_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    attachments: Optional[List[str]] = None,
):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    if not smtp_user or not smtp_password:
        raise RuntimeError("SMTP credentials not set")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content("HTML email not supported")
    msg.add_alternative(html_body, subtype="html")

    for path in attachments or []:
        with open(path, "rb") as f:
            data = f.read()
            filename = os.path.basename(path)

        msg.add_attachment(
            data,
            maintype="application",
            subtype="octet-stream",
            filename=filename,
        )

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)

    return True