from fastapi import APIRouter, Request, Depends
import logging
import re
from typing import Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_

from app.db import get_db
from app.models.vendor_call import VendorCall
from app.models.call_attachments import CallAttachments
from app.models.email_log import EmailLog
from app.services.call_finalizer import finalize_call_once

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


# ----------------------------
# Helpers
# ----------------------------

def _to_int(v) -> Optional[int]:
    try:
        if v is None or isinstance(v, bool):
            return None
        return int(str(v).strip())
    except Exception:
        return None


def _norm_phone(v) -> str:
    if not v:
        return ""
    digits = re.sub(r"\D", "", str(v))
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if digits:
        return f"+{digits}"
    return ""


def _parse_vendor_call_ref(vendor_call_ref: str) -> Tuple[Optional[int], str]:
    if not vendor_call_ref or ":" not in vendor_call_ref:
        return None, ""
    left, right = vendor_call_ref.split(":", 1)
    return _to_int(left), _norm_phone(right)


async def _load_vendor_call_by_project_phone(db, project_request_id, phone):
    res = await db.execute(
        select(VendorCall)
        .where(
            and_(
                VendorCall.project_request_id == project_request_id,
                VendorCall.vendor_phone == phone,
            )
        )
        .order_by(desc(VendorCall.created_at))
    )
    return res.scalars().first()


async def _load_vendor_call_by_retell_call_id(db, call_id):
    res = await db.execute(
        select(VendorCall).where(VendorCall.retell_call_id == call_id)
    )
    return res.scalar_one_or_none()


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    event_type = payload.get("event")

    if event_type not in {"call_analyzed", "call_ended"}:
        return {"ok": True}

    call = payload.get("call") or {}
    call_id = call.get("call_id")

    if not call_id:
        return {"ok": True}

    metadata = call.get("metadata") or {}

    vendor_call_id = _to_int(metadata.get("vendor_call_id"))
    project_request_id = _to_int(metadata.get("project_request_id"))
    vendor_phone = _norm_phone(metadata.get("to_number"))

    attachment_ids = [
        x for x in (metadata.get("attachments") or []) if isinstance(x, int)
    ]

    # ----------------------------
    # Resolve VendorCall
    # ----------------------------
    vendor_call = None

    if vendor_call_id:
        res = await db.execute(
            select(VendorCall).where(VendorCall.id == vendor_call_id)
        )
        vendor_call = res.scalar_one_or_none()

    if not vendor_call and project_request_id and vendor_phone:
        vendor_call = await _load_vendor_call_by_project_phone(
            db, project_request_id, vendor_phone
        )

    if not vendor_call:
        vendor_call = await _load_vendor_call_by_retell_call_id(db, call_id)

    if not vendor_call:
        logger.error("❌ VendorCall not found | call_id=%s", call_id)
        return {"ok": True}

    # ----------------------------
    # 🔒 FINALIZATION GATE
    # ----------------------------
    first_time = await finalize_call_once(
        db=db,
        vendor_call_id=vendor_call.id,
    )

    if not first_time:
        logger.warning(
            "🛑 Duplicate webhook ignored | call_id=%s vendor_call_id=%s",
            call_id,
            vendor_call.id,
        )
        return {"ok": True}

    # ----------------------------
    # Persist retell_call_id
    # ----------------------------
    if not vendor_call.retell_call_id:
        vendor_call.retell_call_id = call_id

    vendor_call.status = "completed"

    # ----------------------------
    # Save attachments (optional)
    # ----------------------------
    if attachment_ids:
        db.add(CallAttachments(call_id=call_id, attachments=attachment_ids))

    await db.commit()

    # ----------------------------
    # AI → EMAIL
    # ----------------------------
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}

    email = (custom.get("email") or "").strip().lower()
    email_confirmed = bool(custom.get("email_confirmed"))

    logger.warning(
        "🧠 ANALYSIS | call_id=%s email=%s confirmed=%s attachments=%s",
        call_id,
        email,
        email_confirmed,
        attachment_ids,
    )

    if not email or not email_confirmed:
        return {"ok": True}

    sent = await db.execute(
        select(EmailLog).where(
            EmailLog.related_call_id == call_id,
            EmailLog.email_type == "retell_vendor",
        )
    )
    if sent.scalar_one_or_none():
        return {"ok": True}

    from app.routes.subcontractor_email import send_vendor_email

    await send_vendor_email(
        payload={
            "vendor_email": email,
            "project_request_id": vendor_call.project_request_id,
            "attachments": attachment_ids,  # may be empty
            "subject": "Project Drawings – BAINS Development",
            "message": "As discussed on the call, here are the project files.",
            "related_call_id": call_id,
        },
        db=db,
    )

    db.add(
        EmailLog(
            project_request_id=vendor_call.project_request_id,
            recipient_email=email,
            email_type="retell_vendor",
            related_call_id=call_id,
        )
    )
    await db.commit()

    logger.warning("✅ EMAIL SENT | call_id=%s", call_id)
    return {"ok": True}