import logging
from backend.app.services.email_service import send_email_with_attachments

logger = logging.getLogger("unified-email")


def send_project_email(
    to_email: str,
    subject: str,
    body: str,
    attachments: list,
):
    """
    Thin wrapper. NO network, NO env access here.
    """

    logger.info(
        "📤 Unified email send → %s | attachments=%d",
        to_email,
        len(attachments),
    )

    return send_email_with_attachments(
        to_email=to_email,
        subject=subject,
        body=body,
        attachments=attachments,
    )