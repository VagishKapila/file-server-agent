import os
import smtplib
import logging
from email.message import EmailMessage
from pathlib import Path

logger = logging.getLogger("email-service")


def send_email_with_attachments(
    to_email: str,
    subject: str,
    body: str,
    attachments: list[dict],
):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("FROM_EMAIL", smtp_user)

    upload_dir = os.getenv("UPLOAD_DIR")
    if not upload_dir:
        raise RuntimeError("UPLOAD_DIR missing")

    upload_path = Path(upload_dir)

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attached = []

    for a in attachments:
        stored = a["stored_filename"]
        name = a["filename"]

        path = upload_path / stored
        if not path.exists():
            logger.error("❌ Missing attachment on disk: %s", path)
            continue

        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="octet-stream",
                filename=name,
            )

        attached.append(name)

    logger.info("📧 Sending email → %s | files=%s", to_email, attached)

    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)