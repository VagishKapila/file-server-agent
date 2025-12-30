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
    event = data.get("event")

    # -----------------------------------
    # 🔒 ONLY process finalized AI output
    # -----------------------------------
    if event != "call_analyzed":
        return {"ok": True}

    call = data.get("call") or {}
    analysis = call.get("call_analysis") or {}
    structured = analysis.get("custom_analysis_data") or {}

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True

    metadata = call.get("metadata") or {}
    vendor_call_id = metadata.get("vendor_call_id")
    retell_call_id = call.get("call_id")
    vendor_phone = call.get("to_number")

    if not email or not confirmed or not vendor_call_id:
        return {"ok": True}

    vendor_call = await db.get(VendorCall, int(vendor_call_id))
    if not vendor_call:
        logger.error("VendorCall missing: %s", vendor_call_id)
        return {"ok": True}

    project_request_id = vendor_call.project_request_id

    # -----------------------------------
    # UPSERT VendorContact
    # -----------------------------------
    res = await db.execute(
        select(VendorContact)
        .where(VendorContact.email == email)
        .where(VendorContact.vendor_phone == vendor_phone)
    )
    contact = res.scalar_one_or_none()

    if not contact:
        contact = VendorContact(
            email=email,
            vendor_phone=vendor_phone,
        )
        db.add(contact)
        await db.flush()

    # -----------------------------------
    # UPDATE VendorCall
    # -----------------------------------
    await db.execute(
        update(VendorCall)
        .where(VendorCall.id == vendor_call.id)
        .values(
            status="confirmed",
            confirmed_at=func.now(),
        )
    )

    # -----------------------------------
    # AUDIT (IMMUTABLE)
    # -----------------------------------
    await db.execute(
        insert(retell_call_audit).values(
            retell_call_id=retell_call_id,
            vendor_call_id=vendor_call.id,
            project_request_id=project_request_id,
            extracted_email=email,
            email_confirmed=True,
            raw_payload=data,
        )
    )

    # -----------------------------------
    # FETCH ATTACHMENTS
    # -----------------------------------
    res = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == project_request_id)
    )
    files = res.scalars().all()

    attachments = [
        {"filename": f.filename, "path": f.stored_path}
        for f in files
        if f.stored_path.startswith("r2://")
    ]

    # -----------------------------------
    # SEND EMAIL (FINAL SIDE EFFECT)
    # -----------------------------------
    send_project_email(
        to_email=email,
        subject="Project Drawings & Files",
        body="Please find the project drawings and photos attached.",
        attachments=attachments,
    )

    await db.commit()

    logger.info(
        "EMAIL SENT | vendor_call_id=%s email=%s attachments=%s",
        vendor_call.id,
        email,
        len(attachments),
    )

    return {"status": "sent"}