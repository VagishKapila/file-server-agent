import os
import logging
import mimetypes
import smtplib
from email.message import EmailMessage

from app.services.r2_download import download_r2_object

logger = logging.getLogger("email-service")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25MB


def send_project_email(to_email, subject, body, attachments):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attached = 0
    skipped_large = []

    for a in attachments:
        path = a.get("path")
        filename = a.get("filename") or a.get("name")

        if not path or not filename:
            continue

        # -------- R2 ONLY (no disk dependency) --------
        data = download_r2_object(path)
        if not data:
            logger.warning("Skipping attachment (download failed): %s", path)
            continue

        # -------- SIZE RULE (future-safe) --------
        if len(data) > MAX_ATTACHMENT_BYTES:
            skipped_large.append(filename)
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

    if skipped_large:
        msg.add_paragraph(
            "\nLarge files were not attached due to email limits:\n"
            + "\n".join(f"- {f}" for f in skipped_large)
        )

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP not configured — email skipped")
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("Email sent to %s | attachments=%s", to_email, attached)
