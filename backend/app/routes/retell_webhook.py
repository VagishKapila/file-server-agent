import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.vendor_contact import VendorContact
from app.models.vendor_call import VendorCall
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

    # ✅ LOCKED DEFENSIVE PARSING
    structured = (
        data.get("custom_analysis")
        or call.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    vendor_phone = call.get("to_number") or call.get("from_number")

    raw_id = call.get("metadata", {}).get("project_request_id")
    try:
        project_request_id = int(raw_id)
    except (TypeError, ValueError):
        logger.warning("RETELL | invalid project_request_id: %s", raw_id)
        return {"ok": True}

    logger.info(
        "RETELL PARSED | email=%s confirmed=%s project_request_id=%s phone=%s",
        email, confirmed, project_request_id, vendor_phone
    )

    if not email or not confirmed:
        return {"ok": True}

    # -----------------------------------
    # 1️⃣ UPSERT VENDOR CONTACT
    # -----------------------------------
    res = await db.execute(
        select(VendorContact).where(VendorContact.email == email)
    )
    vendor_contact = res.scalar_one_or_none()

    if not vendor_contact:
        vendor_contact = VendorContact(
            email=email,
            vendor_phone=vendor_phone,
        )
        db.add(vendor_contact)
        await db.flush()  # get ID without commit
        logger.info("✅ VendorContact created id=%s", vendor_contact.id)
    else:
        logger.info("ℹ️ VendorContact exists id=%s", vendor_contact.id)

    # -----------------------------------
    # 2️⃣ LINK TO EXISTING VENDOR CALL (SAFE)
    # -----------------------------------
    call_res = await db.execute(
        select(VendorCall).where(
            VendorCall.project_request_id == project_request_id,
            VendorCall.vendor_phone == vendor_phone,
        )
    )
    vendor_call = call_res.scalar_one_or_none()

    if vendor_call:
        vendor_call.status = "confirmed"
        vendor_call.confirmed_at = None  # optional, keep if already used elsewhere
        logger.info(
            "🔗 VendorCall linked | call_id=%s contact_id=%s",
            vendor_call.id,
            vendor_contact.id,
        )
    else:
        logger.info("ℹ️ No VendorCall found to link (safe skip)")

    await db.commit()

    # -----------------------------------
    # 3️⃣ SEND ATTACHMENTS (UNCHANGED)
    # -----------------------------------
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

    send_project_email(
        to_email=email,
        subject="Project Files",
        body="Please find drawings and photos attached.",
        attachments=attachments,
    )

    logger.info("🔥 EMAIL SENT | attachments=%s", len(attachments))

    return {
        "status": "sent",
        "email": email,
        "attachments": len(attachments),
        "vendor_contact_id": vendor_contact.id,
        "vendor_call_id": vendor_call.id if vendor_call else None,
    }