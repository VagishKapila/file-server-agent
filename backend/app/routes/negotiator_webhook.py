# retell_webhook.py

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

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


# ----------------------------
# Helpers
# ----------------------------

def _to_int(v) -> Optional[int]:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        if isinstance(v, int):
            return v
        s = str(v).strip()
        if s == "":
            return None
        return int(s)
    except Exception:
        return None


def _norm_phone(v) -> str:
    """
    Normalize phone for matching:
    - strip whitespace
    - keep digits only
    - if 11 digits and starts with 1 -> +<digits>
    - if 10 digits -> +1<digits>
    - else if starts with + already, keep +digits
    """
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""

    # If already has +, keep it but strip non-digits after it
    if s.startswith("+"):
        digits = re.sub(r"\D", "", s)
        return f"+{digits}" if digits else ""

    digits = re.sub(r"\D", "", s)

    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) > 0:
        # last resort, still prefix +
        return f"+{digits}"

    return ""


def _parse_vendor_call_ref(vendor_call_ref: str) -> Tuple[Optional[int], str]:
    """
    Expect something like:
      777: 14084106151
      777:+14084106151
    Returns (project_request_id_int, normalized_phone)
    """
    if not vendor_call_ref:
        return None, ""

    s = str(vendor_call_ref).strip()
    if ":" not in s:
        return None, ""

    left, right = s.split(":", 1)
    project_id = _to_int(left)
    phone = _norm_phone(right)
    return project_id, phone


async def _load_vendor_call_by_id(db: AsyncSession, vendor_call_id: int) -> Optional[VendorCall]:
    res = await db.execute(select(VendorCall).where(VendorCall.id == vendor_call_id))
    return res.scalar_one_or_none()


async def _load_vendor_call_by_project_phone(
    db: AsyncSession, project_request_id: int, vendor_phone_norm: str
) -> Optional[VendorCall]:
    res = await db.execute(
        select(VendorCall).where(
            and_(
                VendorCall.project_request_id == project_request_id,
                VendorCall.vendor_phone == vendor_phone_norm,
            )
        ).order_by(desc(VendorCall.created_at))
    )
    return res.scalars().first()


async def _load_vendor_call_by_retell_call_id(db: AsyncSession, call_id: str) -> Optional[VendorCall]:
    res = await db.execute(select(VendorCall).where(VendorCall.retell_call_id == call_id))
    return res.scalar_one_or_none()


async def _load_most_recent_by_phone(db: AsyncSession, vendor_phone_norm: str) -> Optional[VendorCall]:
    """
    Last-resort fallback: if metadata project id is wrong/missing but phone matches, use most recent.
    This is dangerous, so we log loudly when it happens.
    """
    if not vendor_phone_norm:
        return None
    res = await db.execute(
        select(VendorCall)
        .where(VendorCall.vendor_phone == vendor_phone_norm)
        .order_by(desc(VendorCall.created_at))
        .limit(1)
    )
    return res.scalars().first()


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    # --------------------------------------------------
    # EVENT GUARD — DO NOT PROCESS EARLY EVENTS
    # --------------------------------------------------
    event_type = payload.get("event")

    if event_type not in {"call_analyzed", "call_ended"}:
        logger.info(
            "⏭️ Ignoring Retell event | event=%s call_id=%s",
            event_type,
            payload.get("call", {}).get("call_id"),
        )
        return {"ok": True}

    # --------------------------------------------------
    # DEBUG: RAW PAYLOAD (KEEP)
    # --------------------------------------------------
    logger.warning("📥 RETELL RAW PAYLOAD: %s", payload)

    # --------------------------------------------------
    # BASIC CALL DATA (Retell uses call.call_id)
    # --------------------------------------------------
    call = payload.get("call") or payload.get("message", {}).get("call") or {}
    event_type = payload.get("event")

    call_id = (call.get("call_id") or call.get("id") or "").strip()
    disconnection_reason = call.get("disconnection_reason") or call.get("endedReason") or call.get("ended_reason")
    call_status = call.get("call_status")

    if not call_id:
        logger.error("❌ Missing call.call_id in Retell payload | event=%s keys=%s", event_type, list(call.keys()))
        return {"ok": True}

    metadata = call.get("metadata") or {}

    logger.warning(
        "🧾 CALL HEADER | event=%s call_id=%s status=%s reason=%s metadata_keys=%s",
        event_type,
        call_id,
        call_status,
        disconnection_reason,
        list(metadata.keys()),
    )

    # --------------------------------------------------
    # Parse metadata (robust + normalized)
    # --------------------------------------------------
    vendor_call_id = _to_int(metadata.get("vendor_call_id"))
    vendor_call_ref = (metadata.get("vendor_call_ref") or "").strip()

    project_request_id = _to_int(metadata.get("project_request_id"))
    vendor_phone_norm = _norm_phone(metadata.get("vendor_phone") or metadata.get("dialed_phone") or metadata.get("to_number"))

    # attachments
    raw_attachments = metadata.get("attachment_ids") or metadata.get("attachments") or []
    if isinstance(raw_attachments, list):
        attachment_ids = [x for x in raw_attachments if isinstance(x, int)]
    else:
        attachment_ids = []

    logger.warning(
        "🧩 META PARSED | call_id=%s vendor_call_id=%s vendor_call_ref=%s project_request_id=%s vendor_phone_norm=%s attachments=%s",
        call_id,
        vendor_call_id,
        vendor_call_ref,
        project_request_id,
        vendor_phone_norm,
        attachment_ids,
    )

    # --------------------------------------------------
    # Resolve VendorCall (SOURCE OF TRUTH: vendor_call_ref)
    # --------------------------------------------------
    vendor_call: Optional[VendorCall] = None
    resolution_path = None

    # 1️⃣ vendor_call_ref (PRIMARY — proven to work)
    if vendor_call_ref:
        ref_project_id, ref_phone = _parse_vendor_call_ref(vendor_call_ref)
        if ref_project_id and ref_phone:
            vendor_call = await _load_vendor_call_by_project_phone(
                db, ref_project_id, ref_phone
            )
            resolution_path = "vendor_call_ref"

        logger.warning(
            "🔎 vendor_call_ref lookup | call_id=%s ref_project_id=%s ref_phone=%s found=%s",
            call_id,
            ref_project_id,
            ref_phone,
            bool(vendor_call),
        )

    # 2️⃣ project_request_id + vendor_phone
    if not vendor_call and project_request_id and vendor_phone_norm:
        vendor_call = await _load_vendor_call_by_project_phone(
            db, project_request_id, vendor_phone_norm
        )
        resolution_path = "project_request_id+vendor_phone"

    # 3️⃣ retell_call_id (secondary)
    if not vendor_call:
        vendor_call = await _load_vendor_call_by_retell_call_id(db, call_id)
        if vendor_call:
            resolution_path = "retell_call_id"

    # 4️⃣ last-resort phone only
    if not vendor_call and vendor_phone_norm:
        vendor_call = await _load_most_recent_by_phone(db, vendor_phone_norm)
        if vendor_call:
            resolution_path = "most_recent_by_phone"

    # --------------------------------------------------
    # If still missing, create placeholder (so email does not get dropped)
    # --------------------------------------------------
    if not vendor_call:
        logger.error(
            "❌ VendorCall NOT FOUND after all lookups | call_id=%s project_request_id=%s vendor_phone_norm=%s vendor_call_ref=%s vendor_call_id=%s",
            call_id,
            project_request_id,
            vendor_phone_norm,
            vendor_call_ref,
            vendor_call_id,
        )

        if project_request_id and vendor_phone_norm:
            # Create a placeholder row to avoid losing email + attachments.
            # This is safer than silently failing, and logs will show it happened.
            vendor_call = VendorCall(
                project_request_id=project_request_id,
                vendor_phone=vendor_phone_norm,
                vendor_name=(metadata.get("vendor") or metadata.get("vendor_name") or "").strip() or None,
                trade=(metadata.get("trade") or "").strip() or None,
                status="completed",
                retell_call_id=call_id,
            )
            db.add(vendor_call)
            await db.commit()
            await db.refresh(vendor_call)
            resolution_path = "placeholder_created"
            logger.error(
                "🧯 Placeholder VendorCall CREATED | call_id=%s vendor_call_id=%s project_request_id=%s vendor_phone=%s",
                call_id,
                vendor_call.id,
                project_request_id,
                vendor_phone_norm,
            )
        else:
            # Hard fail (but still return ok so Retell does not retry forever)
            return {"ok": True}

    logger.warning(
        "✅ VendorCall RESOLVED | call_id=%s vendor_call_id=%s resolution_path=%s project_request_id=%s vendor_phone=%s",
        call_id,
        vendor_call.id,
        resolution_path,
        vendor_call.project_request_id,
        vendor_call.vendor_phone,
    )

    # --------------------------------------------------
    # Link retell_call_id (ONCE) + status update
    # --------------------------------------------------
    if not vendor_call.retell_call_id:
        vendor_call.retell_call_id = call_id

    # Only mark completed if call is ended/analyzed
    if event_type in {"call_ended", "call_analyzed"}:
        vendor_call.status = "completed"

    # --------------------------------------------------
    # Save attachments (ONCE PER CALL)
    # --------------------------------------------------
    if attachment_ids:
        existing = await db.execute(select(CallAttachments).where(CallAttachments.call_id == call_id))
        if not existing.scalar_one_or_none():
            db.add(CallAttachments(call_id=call_id, attachments=attachment_ids))
            logger.warning(
                "📎 Attachments persisted | call_id=%s count=%d attachments=%s",
                call_id,
                len(attachment_ids),
                attachment_ids,
            )

    await db.commit()

    # --------------------------------------------------
    # AI ANALYSIS → EMAIL GATE (call_analyzed expected)
    # --------------------------------------------------
    analysis = call.get("call_analysis") or {}
    custom = analysis.get("custom_analysis_data") or {}

    email = (custom.get("email") or "").strip().lower()
    email_confirmed = bool(custom.get("email_confirmed") or custom.get("Email Confirmed"))

    logger.warning(
        "🧠 ANALYSIS PARSED | call_id=%s email=%s email_confirmed=%s has_attachments=%s",
        call_id,
        email,
        email_confirmed,
        bool(attachment_ids),
    )

    if not email:
        logger.error("❌ No email captured | call_id=%s", call_id)
        return {"ok": True}

    if not email_confirmed:
        logger.warning("⚠️ Email not confirmed | call_id=%s email=%s", call_id, email)
        return {"ok": True}

    if not attachment_ids:
        logger.error("❌ Email blocked — no attachments | call_id=%s", call_id)
        return {"ok": True}

    # --------------------------------------------------
    # Prevent duplicate sends
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
        "📤 SENDING EMAIL | call_id=%s vendor_call_id=%s project_request_id=%s email=%s attachments=%s",
        call_id,
        vendor_call.id,
        vendor_call.project_request_id,
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

    logger.warning(
        "✅ EMAIL SENT | call_id=%s vendor_call_id=%s attachments=%d",
        call_id,
        vendor_call.id,
        len(attachment_ids),
    )

    return {"ok": True}