from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import hashlib
import re
import logging

from app.db import get_db
from app.services.inbound_email_matcher import match_inbound_email
from app.services.material_bid_creator import create_material_bid_from_email
from app.services.material_bid_parser import parse_material_bid
from app.services.client_reply_forwarder import forward_vendor_reply_to_client

router = APIRouter()
logger = logging.getLogger(__name__)


def extract_message_id(headers: str | None) -> str | None:
    """
    Extract RFC Message-ID from raw email headers.
    """
    if not headers:
        return None

    match = re.search(
        r"Message-ID:\s*<?([^>\s]+)>?",
        headers,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def generate_fallback_message_id(
    from_email: str,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """
    Deterministic fallback ID to ensure idempotency
    when Message-ID is missing.
    """
    raw = f"{from_email}|{to_email}|{subject}|{body}"
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("/sendgrid/inbound")
async def inbound_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()

    headers = form.get("headers")
    subject = form.get("subject", "")
    from_email = form.get("from", "")
    to_email = form.get("to", "")
    text_body = form.get("text", "")
    html_body = form.get("html", "")

    # 🔐 Message-ID handling
    message_id = extract_message_id(headers)

    if not message_id:
        message_id = generate_fallback_message_id(
            from_email,
            to_email,
            subject,
            text_body or html_body,
        )

    logger.info(
        "Inbound email received",
        extra={
            "message_id": message_id,
            "from": from_email,
            "to": to_email,
            "subject": subject,
        },
    )

    # 1️⃣ Idempotent insert
    try:
        result = await db.execute(
            text("""
                INSERT INTO inbound_emails
                (message_id, from_email, to_email, subject, raw_text, raw_html)
                VALUES (:message_id, :from_email, :to_email, :subject, :raw_text, :raw_html)
                ON CONFLICT (message_id) DO NOTHING
                RETURNING id
            """),
            {
                "message_id": message_id,
                "from_email": from_email,
                "to_email": to_email,
                "subject": subject,
                "raw_text": text_body,
                "raw_html": html_body,
            },
        )

        row = result.fetchone()
        if not row:
            await db.rollback()
            return {"status": "duplicate"}

        inbound_email_id = row[0]
        await db.commit()

    except Exception:
        await db.rollback()
        raise

    # 2️⃣ Match email to project
    project_id = await match_inbound_email(inbound_email_id, db)
    if not project_id:
        return {"status": "ignored"}

    # 3️⃣ Create material bid (idempotent by inbound_email_id)
    material_bid_id = await create_material_bid_from_email(
        inbound_email_id=inbound_email_id,
        db=db,
    )

    # 4️⃣ Parse material bid
    if material_bid_id:
        await parse_material_bid(material_bid_id)

    # 5️⃣ Forward vendor reply to client
    client = await db.execute(
        text("""
            SELECT email FROM user_profiles
            WHERE id = (
                SELECT user_id FROM project_requests
                WHERE id = :pid
            )
        """),
        {"pid": project_id},
    )

    client_row = client.mappings().first()

    if client_row:
        await forward_vendor_reply_to_client(
            client_row["email"],
            from_email,
            subject,
            text_body or html_body,
        )

    return {"status": "ok"}