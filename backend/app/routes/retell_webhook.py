import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.sql import func

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.vendor_contacts import VendorContact
from app.models.vendor_calls import VendorCall
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

    call = data.get("call", {})

    # ---- Defensive parsing (KEEP) ----
    structured = (
        data.get("custom_analysis")
        or call.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True

    raw_project_id = call.get("metadata", {}).get("project_request_id")
    vendor_call_id = call.get("metadata", {}).get("vendor_call_id")
    vendor_phone = call.get("to_number")
    trade = call.get("metadata", {}).get("trade")

    try:
        project_request_id = int(raw_project_id)
    except (TypeError, ValueError):
        logger.warning("RETELL | invalid project_request_id: %s", raw_project_id)
        return {"ok": True}

    logger.info(
        "RETELL PARSED | email=%s confirmed=%s project_request_id=%s vendor_call_id=%s",
        email,
        confirmed,
        project_request_id,
        vendor_call_id,
    )

    if not email or not confirmed:
        return {"ok": True}

    # ---- Save / get VendorContact ----
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
        await db.flush()  # get ID without commit

    # ---- Link VendorCall (NEW PART) ----
    if vendor_call_id:
        await db.execute(
            update(VendorCall)
            .where(VendorCall.id == int(vendor_call_id))
            .values(
                status="confirmed",
                confirmed_at=func.now(),
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

    logger.info("🔥 EMAIL SENT | attachments=%s", len(attachments))

    return {
        "status": "sent",
        "email": email,
        "attachments": len(attachments),
        "vendor_contact_id": vendor_contact.id,
        "vendor_call_id": vendor_call_id,
    }