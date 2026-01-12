from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db
from app.services.inbound_email_matcher import match_inbound_email
from app.services.material_bid_creator import create_material_bid_from_email
from app.services.material_bid_parser import parse_material_bid

router = APIRouter()


@router.post("/sendgrid/inbound")
async def inbound_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()

    headers = form.get("headers", "")
    subject = form.get("subject", "")
    from_email = form.get("from", "")
    to_email = form.get("to", "")
    text_body = form.get("text", "")
    html_body = form.get("html", "")

    # 1️⃣ Save inbound email
    result = await db.execute(
        text("""
            INSERT INTO inbound_emails
            (message_id, from_email, to_email, subject, raw_text, raw_html)
            VALUES (:message_id, :from_email, :to_email, :subject, :raw_text, :raw_html)
            RETURNING id
        """),
        {
            "message_id": headers,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "raw_text": text_body,
            "raw_html": html_body,
        },
    )
    inbound_email_id = result.scalar_one()
    await db.commit()

    # 2️⃣ Match to project
    project_id = await match_inbound_email(inbound_email_id, db)
    if not project_id:
        return {"status": "ignored"}

    # 3️⃣ Create material bid
    material_bid_id = await create_material_bid_from_email(
        inbound_email_id=inbound_email_id,
        db=db,
    )

    # 4️⃣ Parse bid
    if material_bid_id:
        await parse_material_bid(material_bid_id, db)

    return {"status": "ok"}