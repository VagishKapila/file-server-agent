import logging
from typing import List, Dict, Any

import boto3
from app.core.config import settings

logger = logging.getLogger("unified-email")


# -------------------------------------------------------------------
# R2 CLIENT (INLINE — NO IMPORTS)
# -------------------------------------------------------------------

def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


# -------------------------------------------------------------------
# PUBLIC EMAIL SENDER (USED EVERYWHERE)
# -------------------------------------------------------------------

def send_project_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    attachments: List[Dict[str, Any]] | None = None,
):
    """
    attachments = [
        {
            "filename": "file.pdf",
            "content": b"...bytes..."
        }
    ]
    """

    from app.services.smtp_mailer import send_email  # 🔑 local import avoids cycles

    prepared_attachments = []

    if attachments:
        for a in attachments:
            if not a.get("filename") or not a.get("content"):
                logger.warning("Skipping invalid attachment: %s", a)
                continue

            prepared_attachments.append(
                (a["filename"], a["content"])
            )

    logger.info(
        "📧 Sending email → %s | attachments=%d",
        to_email,
        len(prepared_attachments),
    )

    send_email(
        to=to_email,
        subject=subject,
        body=body,
        attachments=prepared_attachments,
    )