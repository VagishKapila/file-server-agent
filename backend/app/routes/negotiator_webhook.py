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
    # DEBUG: RAW PAYLOAD (TEMP – REQUIRED)
    # --------------------------------------------------
    logger.warning("📥 RETELL RAW PAYLOAD: %s", payload)

    # --------------------------------------------------
    # BASIC CALL DATA
    # --------------------------------------------------
    call = payload.get("call") or payload.get("message", {}).get("call") or {}
    call_id = call.get("id")
    ended_reason = call.get("endedReason")

    if not call_id:
        logger.error("❌ Missing call.id")
        return {"ok": True}

    metadata = call.get("metadata") or {}

    # --------------------------------------------------
    # RESOLVE ATTACHMENTS (KEY FIX)
    # --------------------------------------------------
    attachment_ids = (
        metadata.get("attachment_ids")
        or metadata.get("attachments")
        or []
    )

    if isinstance(attachment_ids, list):
        attachment_ids = [x for x in attachment_ids if isinstance(x, int)]
    else:
        attachment_ids = []

    # --------------------------------------------------
    # RESOLVE VENDOR CALL ID (SOURCE OF TRUTH)
    # --------------------------------------------------
    vendor_call_id = metadata.get("vendor_call_id")

    if not vendor_call_id:
        logger.error("❌ vendor_call_id missing in metadata | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # ENSURE VendorCall EXISTS (DO NOT DUPLICATE)
    # --------------------------------------------------
    existing_vc = await db.execute(
        select(VendorCall).where(VendorCall.id == vendor_call_id)
    )
    vendor_call = existing_vc.scalar_one_or_none()

    if not vendor_call:
        logger.error(
            "❌ VendorCall not found | vendor_call_id=%s call_id=%s",
            vendor_call_id,
            call_id,
        )
        return {"ok": True}

    # Link retell call id if missing
    if not vendor_call.retell_call_id:
        vendor_call.retell_call_id = call_id
        vendor_call.status = "completed"

    # --------------------------------------------------
    # SAVE ATTACHMENTS (CRITICAL FOR EMAIL)
    # --------------------------------------------------
    if attachment_ids:
        existing_ca = await db.execute(
            select(CallAttachments).where(CallAttachments.call_id == call_id)
        )
        if not existing_ca.scalar_one_or_none():
            db.add(
                CallAttachments(
                    call_id=call_id,
                    attachments=attachment_ids,
                )
            )
            logger.info(
                "📎 Attachments saved | call_id=%s count=%d",
                call_id,
                len(attachment_ids),
            )

    await db.commit()

    # --------------------------------------------------
    # AI ANALYSIS → EMAIL LOGIC (NO SILENT EXIT)
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

    # Prevent duplicate sends
    existing_email = await db.execute(
        select(EmailLog).where(
            EmailLog.related_call_id == call_id,
            EmailLog.email_type == "retell_vendor",
        )
    )
    if existing_email.scalar_one_or_none():
        logger.warning("⚠️ Email already sent | call_id=%s", call_id)
        return {"ok": True}

    if not attachment_ids:
        logger.error("❌ Email blocked — no attachments | call_id=%s", call_id)
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
        "✅ EMAIL SENT | call_id=%s email=%s attachments=%d",
        call_id,
        email,
        len(attachment_ids),
    )

    return {"ok": True}