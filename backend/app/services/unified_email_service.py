import os
import logging
import tempfile
import requests
from email.message import EmailMessage
import smtplib
from typing import List, Dict

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
    attachments may contain:
    - { filename, path }   (local)
    - { filename, url }    (remote HTTP)
    """

    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attached = 0

    for a in attachments:
        filename = a.get("filename")

        # -------------------------
        # CASE 1: HTTP URL
        # -------------------------
        if "url" in a:
            try:
                logger.info("⬇️ Downloading attachment %s", a["url"])
                r = requests.get(a["url"], timeout=30)
                r.raise_for_status()

                with tempfile.NamedTemporaryFile(delete=False) as tmp:
                    tmp.write(r.content)
                    path = tmp.name

            except Exception as e:
                logger.error("❌ Failed to download %s: %s", a["url"], e)
                continue

        # -------------------------
        # CASE 2: Local path
        # -------------------------
        else:
            path = a.get("path")
            if not path or not os.path.exists(path):
                logger.error("❌ Attachment missing on disk: %s", path)
                continue

        # -------------------------
        # ATTACH
        # -------------------------
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