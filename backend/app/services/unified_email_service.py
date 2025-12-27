import os
import logging
from typing import List, Dict
from email.message import EmailMessage
import smtplib

logger = logging.getLogger("email-service")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)


def send_project_email(
    to_email: str,
    subject: str,
    body: str,
    attachments: List[Dict],
):
    """
    attachments = [
        {
            "filename": "AI_Report.pdf",
            "path": "/data/uploads/projects/0/xxxx.pdf"
        }
    ]
    """

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attached = 0

    for a in attachments:
        path = a.get("path")
        filename = a.get("filename")

        if not path or not os.path.exists(path):
            logger.error("❌ Attachment missing on disk: %s", path)
            continue

        with open(path, "rb") as f:
            data = f.read()

        msg.add_attachment(
            data,
            maintype="application",
            subtype="pdf",
            filename=filename,
        )
        attached += 1

    logger.info("📎 Attachments added: %d", attached)

    if attached == 0:
        raise RuntimeError("No attachments attached — aborting email")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("📩 Email sent to %s with %d attachments", to_email, attached)