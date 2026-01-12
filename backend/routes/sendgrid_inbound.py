from fastapi import APIRouter, Request
from app.db import database
from app.services.inbound_email_matcher import match_inbound_email
from app.services.material_bid_creator import create_material_bid_from_email
from app.services.material_bid_parser import parse_material_bid

router = APIRouter()

@router.post("/sendgrid/inbound")
async def inbound_email(request: Request):
    """
    Handles SendGrid Inbound Parse webhook
    """

    form = await request.form()

    headers = form.get("headers", "")
    subject = form.get("subject", "")
    from_email = form.get("from", "")
    text_body = form.get("text", "")
    html_body = form.get("html", "")
    body = text_body or html_body

    # 1️⃣ Save inbound email
    inbound_email_id = await database.execute("""
        INSERT INTO inbound_emails
        (message_id, from_email, to_email, subject, raw_text, raw_html)
        VALUES (:message_id, :from_email, :to_email, :subject, :raw_text, :raw_html)
        RETURNING id
    """, {
        "message_id": headers,
        "from_email": from_email,
        "to_email": form.get("to", ""),
        "subject": subject,
        "raw_text": text_body,
        "raw_html": html_body,
    })

    # 2️⃣ Match inbound email → project / material request
    project_id = await match_inbound_email(inbound_email_id)

    if not project_id:
        await database.execute("""
            INSERT INTO inbound_email_unmatched
            (inbound_email_id, reason)
            VALUES (:id, 'no_matching_project')
        """, {"id": inbound_email_id})

        return {"status": "ignored"}

    # 3️⃣ Create material bid
    material_bid_id = await create_material_bid_from_email(inbound_email_id)

    # 4️⃣ AI parse bid content
    if material_bid_id:
        await parse_material_bid(material_bid_id)

    return {"status": "ok"}