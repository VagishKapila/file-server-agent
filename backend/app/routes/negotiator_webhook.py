from fastapi import APIRouter, Request, Depends
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.vendor_call import VendorCall
from app.models.call_attachments import CallAttachments
from app.models.email_log import EmailLog

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()

    # --------------------------------------------------
    # DEBUG: RAW PAYLOAD (KEEP — VERY IMPORTANT)
    # --------------------------------------------------
    logger.warning("📥 RETELL RAW PAYLOAD: %s", payload)

    # --------------------------------------------------
    # BASIC CALL DATA
    # --------------------------------------------------
    call = payload.get("call") or payload.get("message", {}).get("call") or {}
    call_id = call.get("id") or call.get("call_id")

    if not call_id:
        logger.error("❌ Missing call_id in Retell payload")
        return {"ok": True}

    metadata = call.get("metadata") or {}

    # --------------------------------------------------
    # RESOLVE vendor_call_ref (SOURCE OF TRUTH)
    # --------------------------------------------------
    vendor_call_ref = metadata.get("vendor_call_ref")

    if not vendor_call_ref:
        logger.error(
            "❌ vendor_call_ref missing | call_id=%s metadata=%s",
            call_id,
            metadata,
        )
        return {"ok": True}

    try:
        project_request_id, vendor_phone = vendor_call_ref.split(":", 1)
        project_request_id = int(project_request_id)
        vendor_phone = vendor_phone.strip()
    except Exception:
        logger.exception(
            "❌ Invalid vendor_call_ref=%s | call_id=%s",
            vendor_call_ref,
            call_id,
        )
        return {"ok": True}

    # --------------------------------------------------
    # LOAD VendorCall (NO DUPLICATES)
    # --------------------------------------------------
    result = await db.execute(
        select(VendorCall).where(
            VendorCall.project_request_id == project_request_id,
            VendorCall.vendor_phone == vendor_phone,
        )
    )
    vendor_call = result.scalar_one_or_none()

    if not vendor_call:
        logger.error(
            "❌ VendorCall NOT FOUND | project=%s vendor_phone=%s call_id=%s",
            project_request_id,
            vendor_phone,
            call_id,
        )
        return {"ok": True}

    # --------------------------------------------------
    # LINK RETELL CALL ID (CRITICAL)
    # --------------------------------------------------
    if not vendor_call.retell_call_id:
        vendor_call.retell_call_id = call_id
        vendor_call.status = "completed"
        logger.info(
            "🔗 Linked retell_call_id | vendor_call_id=%s call_id=%s",
            vendor_call.id,
            call_id,
        )

    # --------------------------------------------------
    # RESOLVE ATTACHMENTS (ROBUST)
    # --------------------------------------------------
    raw_attachments = (
        metadata.get("attachment_ids")
        or metadata.get("attachments")
        or []
    )

    if isinstance(raw_attachments, list):
        attachment_ids = [x for x in raw_attachments if isinstance(x, int)]
    else:
        attachment_ids = []

    logger.info(
        "📎 Parsed attachments | call_id=%s attachments=%s",
        call_id,
        attachment_ids,
    )

    # --------------------------------------------------
    # SAVE ATTACHMENTS (ONCE PER CALL)
    # --------------------------------------------------
    if attachment_ids:
        existing = await db.execute(
            select(CallAttachments).where(CallAttachments.call_id == call_id)
        )
        if not existing.scalar_one_or_none():
            db.add(
                CallAttachments(
                    call_id=call_id,
                    attachments=attachment_ids,
                )
            )
            logger.info(
                "📎 Attachments persisted | call_id=%s count=%d",
                call_id,
                len(attachment_ids),
            )

    await db.commit()

    # --------------------------------------------------
    # AI ANALYSIS → EMAIL GATE
    # --------------------------------------------------
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}

    email = (custom.get("email") or "").strip().lower()
    email_confirmed = bool(
        custom.get("email_confirmed")
        or custom.get("Email Confirmed")
    )

    if not email:
        logger.error("❌ No email captured | call_id=%s", call_id)
        return {"ok": True}

    if not email_confirmed:
        logger.warning(
            "⚠️ Email not confirmed | call_id=%s email=%s",
            call_id,
            email,
        )
        return {"ok": True}

    if not attachment_ids:
        logger.error("❌ Email blocked — no attachments | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # PREVENT DUPLICATE EMAILS
    # --------------------------------------------------
    sent = await db.execute(
        select(EmailLog).where(
            EmailLog.related_call_id == call_id,
            EmailLog.email_type == "retell_vendor",
        )
    )
    if sent.scalar_one_or_none():
        logger.warning("⚠️ Email already sent | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------
    from app.routes.subcontractor_email import send_vendor_email

    logger.warning(
        "📤 SENDING EMAIL | call_id=%s email=%s attachments=%s",
        call_id,
        email,
        attachment_ids,
    )

    try:
        await send_vendor_email(
            payload={
                "vendor_email": email,
                "attachments": attachment_ids,
                "subject": "Project Drawings – BAINS Development",
                "message": "As discussed on the call, attached are the project files.",
            },
            db=db,
        )
    except Exception:
        logger.exception("❌ EMAIL SEND FAILED | call_id=%s", call_id)
        raise

    db.add(
        EmailLog(
            project_request_id=vendor_call.project_request_id,
            recipient_email=email,
            email_type="retell_vendor",
            related_call_id=call_id,
        )
    )
    await db.commit()

    logger.info(
        "✅ EMAIL SENT | call_id=%s vendor_call_id=%s attachments=%d",
        call_id,
        vendor_call.id,
        len(attachment_ids),
    )

    return {"ok": True}