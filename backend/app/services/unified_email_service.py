import os
import logging
from email.message import EmailMessage
import smtplib

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
        # ✅ NORMALIZE KEYS (THIS FIXES THE CRASH)
        path = a.get("path")
        filename = a.get("filename") or a.get("name")

        if not path or not filename:
            logger.warning("Skipping attachment (missing data): %s", a)
            continue

        if not os.path.exists(path):
            logger.warning("Skipping missing file on disk: %s", path)
            continue

        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=filename,
            )
            attached += 1

    logger.info("Attachments added: %d", attached)

    # ✅ DO NOT CRASH SERVER IF SMTP IS MISCONFIGURED
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP env not set — email not sent")
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("Email sent to %s", to_email)