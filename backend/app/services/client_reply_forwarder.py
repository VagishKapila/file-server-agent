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
    CC vendor reply to client automatically
    """

    message = Mail(
        from_email=("noreply@bainsdevcommercial.com", "BAINS Materials AI"),
        to_emails=client_email,
        subject=f"[Vendor Reply] {subject}",
        plain_text_content=f"""
Vendor: {vendor_email}

--- Reply ---
{body}
""",
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    sg.send(message)
