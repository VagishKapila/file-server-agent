import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.services.outreach_toggle import is_global_material_outreach_enabled


async def send_material_email(
    *,
    project_id: int,
    supplier_id: int,
    to_email: str,
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    db: AsyncSession,
):
    enabled = await is_global_material_outreach_enabled(db)

    if not enabled:
        await db.execute(
            text("""
                INSERT INTO supplier_outreach
                (project_id, supplier_id, channel, from_name, from_email,
                 to_email, subject, status)
                VALUES
                (:project_id, :supplier_id, 'email',
                 :from_name, :from_email, :to_email, :subject, 'blocked')
            """),
            {
                "project_id": project_id,
                "supplier_id": supplier_id,
                "from_name": sender_name,
                "from_email": sender_email,
                "to_email": to_email,
                "subject": subject,
            },
        )
        await db.commit()
        return {"status": "blocked_global_outreach_off"}

    message = Mail(
        from_email=(sender_email, sender_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=body,
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sg.send(message)
    message_id = response.headers.get("X-Message-Id")

    await db.execute(
        text("""
            INSERT INTO supplier_outreach
            (project_id, supplier_id, channel, from_name, from_email,
             to_email, subject, message_id, status)
            VALUES
            (:project_id, :supplier_id, 'email',
             :from_name, :from_email, :to_email, :subject, :message_id, 'sent')
        """),
        {
            "project_id": project_id,
            "supplier_id": supplier_id,
            "from_name": sender_name,
            "from_email": sender_email,
            "to_email": to_email,
            "subject": subject,
            "message_id": message_id,
        },
    )

    await db.commit()
    return {"status": "sent", "message_id": message_id}