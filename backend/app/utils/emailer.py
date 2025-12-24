import smtplib
from email.message import EmailMessage
from typing import List

SMTP_HOST = "localhost"
SMTP_PORT = 25
FROM_EMAIL = "ops@yourdomain.com"

def send_email(
    to: str,
    subject: str,
    body: str,
    attachments: List[str] = None
):
    msg = EmailMessage()
    msg["From"] = FROM_EMAIL
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    attachments = attachments or []
    for path in attachments:
        try:
            with open(path, "rb") as f:
                data = f.read()
            filename = path.split("/")[-1]
            msg.add_attachment(
                data,
                maintype="application",
                subtype="octet-stream",
                filename=filename,
            )
        except Exception:
            continue  # attachment failure never blocks email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.send_message(msg)
