from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import random
import os

SENDERS = [
    {"name": "Jessica", "email": "jessica@bainsdevelopment.com"},
    {"name": "Rita", "email": "rita@bainsdevelopment.com"},
    {"name": "Kathy", "email": "kathy@bainsdevelopment.com"},
    {"name": "Kristen", "email": "kristen@bainsdevelopment.com"},
]

def send_material_email(
    to_email: str,
    subject: str,
    body: str,
    project_id: int,
    supplier_id: int,
    db
):
    sender = random.choice(SENDERS)

    message = Mail(
        from_email=(sender["email"], sender["name"]),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sg.send(message)

    db.execute("""
        INSERT INTO supplier_outreach
        (project_id, supplier_id, channel, from_name, from_email,
         to_email, subject, message_id, status)
        VALUES (%s,%s,'email',%s,%s,%s,%s,%s,'sent')
    """, (
        project_id,
        supplier_id,
        sender["name"],
        sender["email"],
        to_email,
        subject,
        response.headers.get("X-Message-Id")
    ))

    return response.status_code
