import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.services.outreach_toggle import is_global_material_outreach_enabled

# 🌍 Lightweight, human-language intros (DO NOT overdo)
LANG_INTRO = {
    "en": "Hello, we are requesting material pricing for a U.S. project.",
    "es": "Hola, estamos solicitando precios de materiales para un proyecto en Estados Unidos.",
    "pt": "Olá, estamos solicitando preços de materiais para um projeto nos Estados Unidos.",
    "zh": "您好，我们正在为美国的一个项目请求材料报价。",
    "it": "Buongiorno, stiamo richiedendo prezzi dei materiali per un progetto negli Stati Uniti.",
}

async def send_material_email(
    project_id: int,
    supplier_id: int,
    to_email: str,
    subject: str,
    body: str,
    sender_name: str,
    sender_email: str,
    lang: str = "en",
):
    """
    Sends outbound material request email.
    BLOCKED if GLOBAL_MATERIAL_OUTREACH is OFF.
    """

    # 🔒 HARD STOP if global outreach is disabled
    enabled = await is_global_material_outreach_enabled()
    if not enabled:
        return {"status": "blocked_global_outreach_off"}

    # 🌍 Select localized intro (default = English)
    intro = LANG_INTRO.get(lang, LANG_INTRO["en"])

    # ✉️ Final email body (clean + human)
    full_body = f"""{intro}

------------------------------------
{body}
------------------------------------
"""

    message = Mail(
        from_email=(sender_email, sender_name),
        to_emails=to_email,
        subject=subject,
        plain_text_content=full_body,
    )

    sg = SendGridAPIClient(os.environ["SENDGRID_API_KEY"])
    response = sg.send(message)

    return {
        "status": "sent",
        "message_id": response.headers.get("X-Message-Id"),