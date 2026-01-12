from fastapi import APIRouter, Request
import app.db as db

from app.services.inbound_email_matcher import match_inbound_email
from app.services.material_bid_creator import create_material_bid_from_email
from app.services.material_bid_parser import parse_material_bid

router = APIRouter()

@router.post("/sendgrid/inbound")
async def inbound_email(request: Request):
    form = await request.form()

    headers = form.get("headers", "")
    subject = form.get("subject", "")
    from_email = form.get("from", "")
    to_email = form.get("to", "")
    text_body = form.get("text", "")
    html_body = form.get("html", "")
    body = text_body or html_body

    # 1️⃣ Save inbound email
    inbound_email_id = db.execute("""
        INSERT INTO inbound_emails
        (message_id, from_email, to_email, subject, raw_text, raw_html)
        VALUES (%s,%s,%s,%s,%s,%s)
        RETURNING id
    """, (
        headers,
        from_email,
        to_email,
        subject,
        text_body,
        html_body,
    ))[0]["id"]

    # 2️⃣ Match inbound email → project/material
    project_id = await match_inbound_email(inbound_email_id)

    if not project_id:
        db.execute("""
            INSERT INTO inbound_email_unmatched
            (inbound_email_id, reason)
            VALUES (%s,'no_matching_project')
        """, (inbound_email_id,))
        return {"status": "ignored"}

    # 3️⃣ Create material bid
    material_bid_id = await create_material_bid_from_email(inbound_email_id)

    # 4️⃣ AI parse bid
    if material_bid_id:
        await parse_material_bid(material_bid_id)

    return {"status": "ok"}
