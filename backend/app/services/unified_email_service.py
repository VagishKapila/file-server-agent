import os
import logging
import mimetypes
import smtplib
import requests
from email.message import EmailMessage

logger = logging.getLogger("email-service")

SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

# REQUIRED for R2 downloads
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")
# example:
# https://<account>.r2.cloudflarestorage.com


def _load_attachment(path: str) -> bytes | None:
    """
    Supports:
      - r2://bucket/key  (Cloudflare R2)
      - local filesystem paths
    """

    # ---------------- R2 ----------------
    if path.startswith("r2://"):
        if not R2_PUBLIC_BASE:
            logger.error("R2_PUBLIC_BASE not set")
            return None

        try:
            # r2://bucket/key
            _, rest = path.split("r2://", 1)
            bucket, key = rest.split("/", 1)
            url = f"{R2_PUBLIC_BASE}/{bucket}/{key}"
        except ValueError:
            logger.error("Invalid r2 path: %s", path)
            return None

        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.error("Failed to fetch R2 object %s: %s", url, e)
            return None

    # ---------------- LOCAL ----------------
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()

    logger.warning("Attachment path not found: %s", path)
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
        filename = a.get("filename") or a.get("name")

        if not path or not filename:
            logger.warning("Skipping attachment (missing fields): %s", a)
            continue

        data = _load_attachment(path)
        if not data:
            logger.warning("Skipping attachment (unable to load): %s", path)
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
        logger.warning("Email sent WITHOUT attachments")

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        logger.error("SMTP env not configured — aborting send")
        return

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

    logger.info("Email sent to %s", to_email)