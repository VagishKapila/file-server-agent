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

    # ONLY process analyzed calls
    if data.get("event") != "call_analyzed":
        return {"ok": True}

    call = data.get("call", {}) or {}

    analysis = (
        data.get("analysis", {}).get("custom_analysis")
        or data.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = analysis.get("email")
    confirmed = analysis.get("email_confirmed") is True
    vendor_phone = call.get("to_number")
    retell_call_id = call.get("call_id")

    logger.error(
        "🔎 ANALYZED | call_id=%s phone=%s email=%s confirmed=%s analysis=%s",
        retell_call_id,
        vendor_phone,
        email,
        confirmed,
        analysis,
    )

    if not email or not confirmed or not vendor_phone:
        return {"ok": True}

    project_request_id = vendor_call.project_request_id

    # ---- VendorContact ----
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

    # ---- Update VendorCall ----
    await db.execute(
        update(VendorCall)
        .where(VendorCall.id == vendor_call.id)
        .values(
            status="confirmed",
            confirmed_at=func.now(),
        )
    )

    # ---- AUDIT (SOURCE OF TRUTH) ----
    await db.execute(
        insert(retell_call_audit).values(
            retell_call_id=retell_call_id,
            to_number=vendor_phone,
            extracted_email=email,
            email_confirmed=confirmed,
            project_request_id=project_request_id,
            vendor_call_id=vendor_call.id,
            raw_payload=data,
        )
    )

    # ---- Fetch project files ----
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

    # ---- Send email ----
    send_project_email(
        to_email=email,
        subject="Project Files",
        body="Please find drawings and photos attached.",
        attachments=attachments,
    )

    await db.commit()

    logger.info(
        "🔥 EMAIL SENT | vendor_call_id=%s attachments=%s",
        vendor_call.id,
        len(attachments),
    )

    return {
        "status": "sent",
        "email": email,
        "vendor_call_id": vendor_call.id,
        "attachments": len(attachments),
    }