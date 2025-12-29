import os
import logging
import mimetypes
import smtplib
from email.message import EmailMessage

from app.services.r2download import download_r2_object

logger = logging.getLogger("email-service")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)


def send_project_email(to_email, subject, body, attachments):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attached = 0

    for a in attachments:
        path = a.get("path")
        filename = a.get("filename")

        if not path or not filename:
            continue

        # ✅ R2 ONLY
        if not path.startswith("r2://"):
            continue

        data = download_r2_object(path)
        if not data:
            continue

        mime_type, _ = mimetypes.guess_type(filename)
        maintype, subtype = (mime_type or "application/octet-stream").split("/", 1)

        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )
        attached += 1

    logger.info("Attachments added: %d", attached)

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP env not configured — aborting send")
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("Email sent to %s", to_email)