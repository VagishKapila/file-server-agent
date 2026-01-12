import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.db import database
from app.services.outreach_toggle import is_global_material_outreach_enabled


async def send_material_email(
    project_id: int,
    supplier_id: int,
    to_email: str,
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str
):
    """
    Sends outbound material request email.
    BLOCKED if GLOBAL_MATERIAL_OUTREACH is OFF.
    """

    # 🔒 HARD GUARD — NO ASSUMPTIONS
    enabled = await is_global_material_outreach_enabled()
    if not enabled:
        await database.execute("""
            INSERT INTO supplier_outreach
            (project_id, supplier_id, channel, from_name, from_email,
             to_email, subject, status)
            VALUES
            (:project_id, :supplier_id, 'email',
             :from_name, :from_email, :to_email, :subject, 'blocked')
        """, {
            "project_id": project_id,
            "supplier_id": supplier_id,
            "from_name": sender_name,
            "from_email": sender_email,
            "to_email": to_email,
            "subject": subject,
        })
        return {"status": "blocked_global_outreach_off"}

    # 📤 SEND EMAIL
    message = Mail(
        from_email=(sender_email, sender_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sg.send(message)

    message_id = response.headers.get("X-Message-Id")

    # 🧾 LOG OUTREACH
    await database.execute("""
        INSERT INTO supplier_outreach
        (project_id, supplier_id, channel, from_name, from_email,
         to_email, subject, message_id, status)
        VALUES
        (:project_id, :supplier_id, 'email',
         :from_name, :from_email, :to_email, :subject, :message_id, 'sent')
    """, {
        "project_id": project_id,
        "supplier_id": supplier_id,
        "from_name": sender_name,
        "from_email": sender_email,
        "to_email": to_email,
        "subject": subject,
        "message_id": message_id,
    })

    return {"status": "sent", "message_id": message_id}
