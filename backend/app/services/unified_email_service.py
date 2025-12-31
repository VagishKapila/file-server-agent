import logging
from typing import List, Dict, Any

from app.services.mailer import send_email  # ← your existing mail sender

logger = logging.getLogger("unified-email")


def send_project_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    attachments: List[Dict[str, Any]] | None = None,
):
    """
    attachments format (FINAL, REQUIRED):
    [
        {
            "filename": "file.pdf",
            "content": b"...raw bytes..."
        }
    ]
    """

    safe_attachments = []

    for a in attachments or []:
        if not a.get("filename") or not a.get("content"):
            logger.warning("Skipping invalid attachment: %s", a)
            continue
        safe_attachments.append(a)

    logger.info(
        "Sending email to %s | attachments=%d",
        to_email,
        len(safe_attachments),
    )

    send_email(
        to=to_email,
        subject=subject,
        body=body,
        attachments=safe_attachments,
    )