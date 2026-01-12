import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

SENDGRID_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("OUTBOUND_FROM_EMAIL", "procurement@bainsdevcommercial.com")

async def forward_vendor_reply_to_client(
    client_email: str,
    vendor_email: str,
    subject: str,
    body: str
):
    if not client_email:
        return

    message = Mail(
        from_email=FROM_EMAIL,
        to_emails=client_email,
        subject=f"Vendor Reply: {subject}",
        plain_text_content=f"""
Vendor Email: {vendor_email}

--- MESSAGE ---
{body}
"""
    )

    sg = SendGridAPIClient(SENDGRID_KEY)
    sg.send(message)
