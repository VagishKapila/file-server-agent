import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.services.outreach_toggle import is_global_material_outreach_enabled
from app.db import get_db

LANG_INTRO = {
    "es": "Hola, estamos solicitando precios de materiales para un proyecto en EE.UU.",
    "pt": "Olá, estamos solicitando preços de materiais para um projeto nos EUA.",
    "zh": "您好，我们正在为美国的一个项目请求材料报价。",
}

async def send_material_email(
    project_id,
    supplier_id,
    to_email,
    subject,
    body,
    sender_name,
    sender_email,
    lang="en",
):
    if not await is_global_material_outreach_enabled():
        return {"status": "blocked"}

    intro = LANG_INTRO.get(lang, "Hello, we are requesting material pricing for a U.S. project.")

    full_body = f"""
{intro}

---------------------
{body}
---------------------
"""

    message = Mail(
        from_email=(sender_email, sender_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=full_body,
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sg.send(message)

    return {"status": "sent", "message_id": response.headers.get("X-Message-Id")}
