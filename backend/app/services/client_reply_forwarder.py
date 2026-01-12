import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

async def forward_vendor_reply_to_client(
    client_email: str,
    vendor_email: str,
    subject: str,
    body: str,
):
    """
    Forward vendor reply to client automatically
    """

    forward_subject = f"[Vendor Reply] {subject}"

    forward_body = f"""
Vendor Email: {vendor_email}

----------------------------
{body}
----------------------------
"""

    message = Mail(
        from_email=os.environ.get("DEFAULT_FROM_EMAIL"),
        to_emails=client_email,
        subject=forward_subject,
        plain_text_content=forward_body,
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    sg.send(message)
