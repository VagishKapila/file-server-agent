from fastapi import APIRouter, Request, Depends
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.vendor_call import VendorCall
from app.models.call_attachments import CallAttachments

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()

    # --------------------------------------------------
    # BASIC CALL DATA
    # --------------------------------------------------
    call = payload.get("call") or payload.get("message", {}).get("call") or {}
    call_id = call.get("id")

    if not call_id:
        return {"ok": True}

    metadata = call.get("metadata") or {}

    vendor_call_ref = metadata.get("vendor_call_ref")
    attachment_ids = metadata.get("attachment_ids", [])

    # Normalize attachments
    if isinstance(attachment_ids, list):
        attachment_ids = [x for x in attachment_ids if isinstance(x, int)]
    else:
        attachment_ids = []

    # --------------------------------------------------
    # CREATE VENDOR CALL (ONCE)
    # --------------------------------------------------
    if vendor_call_ref:
        try:
            project_request_id, vendor_phone = vendor_call_ref.split(":", 1)
            project_request_id = int(project_request_id)
        except Exception:
            logger.error("❌ Invalid vendor_call_ref | %s", vendor_call_ref)
            project_request_id = None
            vendor_phone = None

        if project_request_id and vendor_phone:
            existing = await db.execute(
                select(VendorCall).where(
                    VendorCall.retell_call_id == call_id
                )
            )
            if not existing.scalar_one_or_none():
                vendor_call = VendorCall(
                    project_request_id=project_request_id,
                    vendor_phone=vendor_phone,
                    retell_call_id=call_id,
                    status="completed",
                )
                db.add(vendor_call)
                await db.flush()

                logger.info(
                    "✅ VendorCall created | call_id=%s project=%s vendor=%s",
                    call_id,
                    project_request_id,
                    vendor_phone,
                )

                # --------------------------------------------------
                # SAVE ATTACHMENTS (CRITICAL FIX)
                # --------------------------------------------------
                if attachment_ids:
                    db.add(
                        CallAttachments(
                            call_id=call_id,
                            attachments=attachment_ids,
                        )
                    )
                    logger.info(
                        "📎 Attachments linked | call_id=%s count=%d",
                        call_id,
                        len(attachment_ids),
                    )

                await db.commit()

    return {"ok": True}