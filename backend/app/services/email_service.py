import os
import logging
import mimetypes
from email.message import EmailMessage
import smtplib
import requests

logger = logging.getLogger("email-service")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

# Must be:
# https://<account-id>.r2.cloudflarestorage.com/<bucket>
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")


def _load_attachment(path: str) -> bytes | None:
    """
    Supports:
      - local filesystem paths
      - r2://bucket/key  → fetched via HTTPS
    """

    # ---------- R2 ----------
    if path.startswith("r2://"):
        if not R2_PUBLIC_BASE:
            logger.error("R2_PUBLIC_BASE not set")
            return None

        # r2://bucket/key → key
        _, _, remainder = path.partition("://")
        _, _, key = remainder.partition("/")

        url = f"{R2_PUBLIC_BASE}/{key}"

        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.error("Failed to fetch R2 object %s: %s", url, e)
            return None

    # ---------- LOCAL FILE ----------
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()

    return None


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

        data = _load_attachment(path)
        if not data:
            logger.warning("Skipping missing attachment: %s", path)
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

    if attached == 0:
        logger.warning("No attachments added — sending email without files")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("Email sent to %s", to_email)


def send_email_with_attachments(to_email, subject, body, attachments):
    send_project_email(
        to_email=to_email,
        subject=subject,
        body=body,
        attachments=attachments,
    )