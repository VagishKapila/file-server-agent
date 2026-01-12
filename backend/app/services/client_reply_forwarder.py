import os
from typing import Optional


async def forward_vendor_reply_to_client(
    client_email: str,
    vendor_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Forward vendor reply to client email.
    Safe to call even if SendGrid is not installed.
    """

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail
    except ImportError:
        # SendGrid not installed yet — fail soft
        return {
            "status": "skipped",
            "reason": "sendgrid_not_installed",
        }

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        return {
            "status": "skipped",
            "reason": "missing_sendgrid_api_key",
        }

    sg = SendGridAPIClient(api_key)

    message = Mail(
        from_email=vendor_email,
        to_emails=client_email,
        subject=f"Vendor Reply: {subject}",
        plain_text_content=body,
    )

    response = sg.send(message)

    return {
        "status": "forwarded",
        "message_id": response.headers.get("X-Message-Id"),
    }