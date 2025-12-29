# app/routes/retell_webhook.py

import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.vendor_contacts import VendorContact
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()

    logger.info("🔥 RETELL WEBHOOK HIT")
    logger.info("🔥 RETELL RAW PAYLOAD: %s", data)

    call = data.get("call", {})

    # ✅ DEFENSIVE PARSING — DO NOT CHANGE
    structured = (
        data.get("custom_analysis")
        or call.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    raw_id = call.get("metadata", {}).get("project_request_id")

    vendor_name = call.get("metadata", {}).get("vendor_name")
    vendor_phone = call.get("metadata", {}).get("original_vendor_phone")

    try:
        project_request_id = int(raw_id)
    except (TypeError, ValueError):
        logger.warning("RETELL | invalid project_request_id: %s", raw_id)
        return {"ok": True}

    logger.info(
        "RETELL PARSED | email=%s confirmed=%s project_request_id=%s",
        email,
        confirmed,
        project_request_id,
    )

    if not email or not confirmed:
        return {"ok": True}

    # ✅ SAVE EMAIL (IDEMPOTENT)
    if vendor_phone:
        existing = await db.execute(
            select(VendorContact).where(
                VendorContact.vendor_phone == vendor_phone,
                VendorContact.email == email,
            )
        )
        existing = existing.scalar_one_or_none()

        if not existing:
            db.add(
                VendorContact(
                    vendor_name=vendor_name,
                    vendor_phone=vendor_phone,
                    email=email,
                )
            )
            await db.commit()
            logger.info("✅ VENDOR EMAIL SAVED | %s", email)
        else:
            logger.info("ℹ️ VENDOR EMAIL ALREADY EXISTS | %s", email)
    else:
        logger.warning("⚠️ vendor_phone missing — email not persisted")

    # 🔍 FETCH PROJECT FILES
    res = await db.execute(
        select(ProjectFile).where(
            ProjectFile.project_request_id == project_request_id
        )
    )
    files = res.scalars().all()

    # ✅ ONLY R2 FILES FOR ATTACHMENTS
    attachments = [
        {"filename": f.filename, "path": f.stored_path}
        for f in files
        if f.stored_path and f.stored_path.startswith("r2://")
    ]

    send_project_email(
        to_email=email,
        subject="Project Drawings & Photos",
        body="Please find drawings and photos attached.",
        attachments=attachments,
    )

    logger.info("🔥 EMAIL SENT | attachments=%s", len(attachments))

    return {
        "status": "sent",
        "email": email,
        "attachments": len(attachments),
    }