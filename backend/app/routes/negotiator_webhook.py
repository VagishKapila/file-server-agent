from fastapi import APIRouter, Request, Depends
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.email_log import EmailLog
from app.models.call_attachments import CallAttachments

router = APIRouter(prefix="/negotiator", tags=["negotiator"])
logger = logging.getLogger("negotiator")


@router.post("/webhook")
async def negotiator_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()

    call = data.get("call") or data.get("message", {}).get("call") or {}
    call_id = call.get("id")
    ended_reason = call.get("endedReason")

    if not call_id or not ended_reason:
        return {"ok": True}

    # --------------------------------------------------
    # AI OUTPUT
    # --------------------------------------------------
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}

    email = custom.get("email")
    email_confirmed = bool(
        custom.get("email_confirmed")
        or custom.get("Email Confirmed")
    )
    interest = custom.get("interest")

    if not (email and email_confirmed and interest in ("yes", "maybe")):
        return {"ok": True}

    normalized_email = email.strip().lower()

    # --------------------------------------------------
    # PREVENT DUPLICATE SENDS
    # --------------------------------------------------
    existing = await db.execute(
        select(EmailLog).where(
            EmailLog.related_call_id == call_id,
            EmailLog.email_type == "retell_vendor",
        )
    )
    if existing.scalar_one_or_none():
        logger.warning("⚠️ Email already sent | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # RESOLVE ATTACHMENT IDS (INTS ONLY)
    # --------------------------------------------------
    attachment_ids = call.get("metadata", {}).get("attachment_ids", [])

    if isinstance(attachment_ids, list):
        attachment_ids = [x for x in attachment_ids if isinstance(x, int)]
    else:
        attachment_ids = []

    # Fallback to DB mapping
    if not attachment_ids:
        row = await db.execute(
            select(CallAttachments).where(CallAttachments.call_id == call_id)
        )
        record = row.scalar_one_or_none()
        if record and isinstance(record.attachments, list):
            attachment_ids = [
                x for x in record.attachments if isinstance(x, int)
            ]

    if not attachment_ids:
        logger.error("❌ No valid attachment IDs | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # SEND VIA SUBCONTRACTOR EMAIL PIPELINE
    # --------------------------------------------------
    from app.routes.subcontractor_email import send_vendor_email

    await send_vendor_email(
        payload={
            "vendor_email": normalized_email,
            "attachments": attachment_ids,
            "subject": "Project Drawings – BAINS Development",
            "message": "As discussed on the call, attached are the project files.",
        },
        db=db,
    )

    # --------------------------------------------------
    # LOG EMAIL
    # --------------------------------------------------
    db.add(
        EmailLog(
            project_request_id=None,
            recipient_email=normalized_email,
            email_type="retell_vendor",
            related_call_id=call_id,
        )
    )
    await db.commit()

    logger.info(
        "✅ Vendor email sent | call_id=%s | attachments=%d",
        call_id,
        len(attachment_ids),
    )

    return {"ok": True}