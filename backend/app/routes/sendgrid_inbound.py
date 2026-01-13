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

# ------------------------------------------------------------
# Message-ID helpers
# ------------------------------------------------------------

def extract_message_id(headers: str | None) -> str | None:
    """
    Extract RFC Message-ID from raw email headers.
    """
    if not headers or not headers.strip():
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
    Deterministic fallback for curl / malformed payloads.
    Guarantees idempotency.
    """
    raw = f"{from_email}|{to_email}|{subject}|{body}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ------------------------------------------------------------
# Inbound SendGrid webhook
# ------------------------------------------------------------

@router.post("/sendgrid/inbound")
async def inbound_email(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    form = await request.form()

    headers = form.get("headers")
    subject = form.get("subject", "") or ""
    from_email = form.get("from", "") or ""
    to_email = form.get("to", "") or ""
    text_body = form.get("text", "") or ""
    html_body = form.get("html", "") or ""

    # --------------------------------------------------------
    # Message-ID (critical)
    # --------------------------------------------------------
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

    # --------------------------------------------------------
    # 1️⃣ Idempotent insert into inbound_emails
    # --------------------------------------------------------
    try:
        result = await db.execute(
            text("""
                INSERT INTO inbound_emails
                (
                    message_id,
                    from_email,
                    to_email,
                    subject,
                    raw_text,
                    raw_html
                )
                VALUES
                (
                    :message_id,
                    :from_email,
                    :to_email,
                    :subject,
                    :raw_text,
                    :raw_html
                )
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
            logger.info(
                "Duplicate inbound email ignored",
                extra={"message_id": message_id},
            )
            return {"status": "duplicate"}

        inbound_email_id = row[0]
        await db.commit()

    except Exception:
        await db.rollback()
        logger.exception("Failed inserting inbound email")
        return {"status": "error"}

    # --------------------------------------------------------
    # 2️⃣–5️⃣ Processing pipeline (guarded)
    # --------------------------------------------------------
    try:
        # 2️⃣ Match email to project
        project_id = await match_inbound_email(inbound_email_id, db)
        if not project_id:
            await db.rollback()
            return {"status": "ignored"}

        # 3️⃣ Create material bid
        material_bid_id = await create_material_bid_from_email(
            inbound_email_id=inbound_email_id,
            db=db,
        )

        # 4️⃣ Parse material bid (non-fatal)
        if material_bid_id:
            try:
                await parse_material_bid(material_bid_id)
            except Exception:
                logger.exception(
                    "Material bid parsing failed",
                    extra={"material_bid_id": material_bid_id},
                )

        # 5️⃣ Forward vendor reply to client
        client = await db.execute(
            text("""
                SELECT email
                FROM user_profiles
                WHERE id = (
                    SELECT user_id
                    FROM project_requests
                    WHERE id = :pid
                )
            """),
            {"pid": project_id},
        )

        client_row = client.mappings().first()

        if client_row:
            try:
                await forward_vendor_reply_to_client(
                    client_row["email"],
                    from_email,
                    subject,
                    text_body or html_body,
                )
            except Exception:
                logger.exception(
                    "Failed forwarding vendor reply to client",
                    extra={"project_id": project_id},
                )

        return {"status": "ok"}

    except Exception as e:
        logger.exception(
            "Inbound email processing failed",
            extra={
                "inbound_email_id": inbound_email_id,
                "error": str(e),
            },
        )
        await db.rollback()
        return {"status": "error"}