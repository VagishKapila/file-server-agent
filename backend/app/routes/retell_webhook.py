import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.sql import func

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.vendor_contacts import VendorContact
from app.models.vendor_call import VendorCall
from app.models.retell_call_audit import retell_call_audit
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()
    logger.info("🔥 RETELL RAW PAYLOAD: %s", data)

    event = data.get("event")

    # ---------------------------------------------------------
    # 🔒 RULE #1: ONLY process finalized AI output
    # Retell guarantees structured AI results ONLY on call_analyzed
    # ---------------------------------------------------------
    if event != "call_analyzed":
        return {"ok": True}

    call = data.get("call") or {}
    analysis = data.get("analysis") or {}

    # ---------------------------------------------------------
    # 🔒 RULE #2: Defensive extraction (RETELL-PROVEN)
    # This matches real dashboard + webhook payloads
    # ---------------------------------------------------------
    structured = (
        analysis.get("custom_analysis")
        or data.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True

    vendor_phone = call.get("to_number")
    retell_call_id = call.get("call_id")

    metadata = call.get("metadata") or {}
    vendor_call_id = metadata.get("vendor_call_id")

    logger.warning(
        "🧪 RETELL FINAL | event=%s call_id=%s phone=%s email=%s confirmed=%s metadata=%s",
        event,
        retell_call_id,
        vendor_phone,
        email,
        confirmed,
        metadata,
    )

    # ---------------------------------------------------------
    # 🔒 RULE #3: Hard guards (NO SIDE EFFECTS if missing)
    # ---------------------------------------------------------
    if not email or not confirmed or not vendor_phone:
        return {"ok": True}

    if not vendor_call_id:
        logger.error("❌ Missing vendor_call_id in Retell metadata")
        return {"ok": True}

    # ---------------------------------------------------------
    # 🔒 RULE #4: Deterministic VendorCall lookup (NO GUESSING)
    # ---------------------------------------------------------
    vendor_call = await db.get(VendorCall, int(vendor_call_id))

    if not vendor_call:
        logger.error(
            "❌ VendorCall not found | vendor_call_id=%s call_id=%s",
            vendor_call_id,
            retell_call_id,
        )
        return {"ok": True}

    project_request_id = vendor_call.project_request_id

    # ---------------------------------------------------------
    # 🔒 RULE #5: UPSERT VendorContact (idempotent)
    # ---------------------------------------------------------
    res = await db.execute(
        select(VendorContact)
        .where(VendorContact.email == email)
        .where(VendorContact.vendor_phone == vendor_phone)
    )
    vendor_contact = res.scalar_one_or_none()

    if not vendor_contact:
        vendor_contact = VendorContact(
            email=email,
            vendor_phone=vendor_phone,
        )
        db.add(vendor_contact)
        await db.flush()

    # ---------------------------------------------------------
    # 🔒 RULE #6: Update VendorCall (single source of truth)
    # ---------------------------------------------------------
    await db.execute(
        update(VendorCall)
        .where(VendorCall.id == vendor_call.id)
        .values(
            status="confirmed",
            confirmed_at=func.now(),
        )
    )

    # ---------------------------------------------------------
    # 🔒 RULE #7: Immutable audit trail (NON-NEGOTIABLE)
    # ---------------------------------------------------------
    await db.execute(
        insert(retell_call_audit).values(
            retell_call_id=retell_call_id,
            to_number=vendor_phone,
            extracted_email=email,
            email_confirmed=True,
            project_request_id=project_request_id,
            vendor_call_id=vendor_call.id,
            raw_payload=data,
        )
    )

    # ---------------------------------------------------------
    # 🔒 RULE #8: Fetch attachments (exact behavior preserved)
    # ---------------------------------------------------------
    res = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == project_request_id)
    )
    files = res.scalars().all()

    attachments = [
        {"filename": f.filename, "path": f.stored_path}
        for f in files
        if f.stored_path and f.stored_path.startswith("r2://")
    ]

    # ---------------------------------------------------------
    # 🔒 RULE #9: Send email (final side effect)
    # ---------------------------------------------------------
    send_project_email(
        to_email=email,
        subject="Project Files",
        body="Please find drawings and photos attached.",
        attachments=attachments,
    )

    await db.commit()

    logger.info(
        "🔥 EMAIL SENT | vendor_call_id=%s email=%s attachments=%s",
        vendor_call.id,
        email,
        len(attachments),
    )

    return {
        "status": "sent",
        "email": email,
        "vendor_call_id": vendor_call.id,
        "attachments": len(attachments),
    }