# app/routes/retell_webhook.py

from fastapi import APIRouter, Request, Depends
import logging
import re
from typing import Optional, Tuple, Any, Dict

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
    if v is None:
        return ""
    s = str(v).strip()
    if s == "":
        return ""

    if s.startswith("+"):
        digits = re.sub(r"\D", "", s)
        return f"+{digits}" if digits else ""

    digits = re.sub(r"\D", "", s)

    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) > 0:
        return f"+{digits}"

    return ""


def _parse_vendor_call_ref(vendor_call_ref: str) -> Tuple[Optional[int], str]:
    if not vendor_call_ref:
        return None, ""

    s = str(vendor_call_ref).strip()
    if ":" not in s:
        return None, ""

    left, right = s.split(":", 1)
    project_id = _to_int(left)
    phone = _norm_phone(right)
    return project_id, phone


def _deep_get(obj: Any, path: str) -> Any:
    """
    Safe nested getter using dot paths.
    Example: _deep_get(call, "call_analysis.custom_analysis_data.email")
    """
    cur = obj
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def extract_email_and_confirmation(call: Dict[str, Any]) -> Tuple[str, bool]:
    """
    Handles schema drift across Retell events.
    Returns: (email_lower_or_empty, confirmed_bool)
    """
    analysis = call.get("call_analysis") or {}

    # Log analysis keys once per event (helps forever)
    try:
        logger.warning(
            "🧠 ANALYSIS KEYS | call_id=%s analysis_keys=%s",
            (call.get("call_id") or "").strip(),
            list(analysis.keys()) if isinstance(analysis, dict) else [],
        )
    except Exception:
        pass

    # Primary location
    custom = analysis.get("custom_analysis_data") or {}
    if not isinstance(custom, dict):
        custom = {}

    email = (
        (custom.get("email") or custom.get("Email") or "").strip()
    )

    # Confirmation can be True/False or string
    raw_confirm = custom.get("email_confirmed") or custom.get("Email Confirmed") or False
    email_confirmed = bool(raw_confirm)

    # Fallbacks (common drift paths)
    if not email:
        candidates = [
            _deep_get(call, "call_analysis.email"),
            _deep_get(call, "call_analysis.extracted_email"),
            _deep_get(call, "call_analysis.entities.email"),
            _deep_get(call, "call_analysis.variables.email"),
            _deep_get(call, "call_analysis.custom.email"),
        ]
        for c in candidates:
            if isinstance(c, str) and c.strip():
                email = c.strip()
                break

    email = email.lower().strip() if isinstance(email, str) else ""
    return email, email_confirmed


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

    event_type = payload.get("event")
    call = payload.get("call") or payload.get("message", {}).get("call") or {}

    call_id = (call.get("call_id") or call.get("id") or "").strip()
    if not call_id:
        logger.error("❌ Missing call_id | event=%s payload_keys=%s", event_type, list(payload.keys()))
        return {"ok": True}

    # Process only the events we care about, but DO NOT hard-finalize globally
    if event_type not in {"call_analyzed", "call_ended"}:
        logger.info("⏭️ Ignoring event | event=%s call_id=%s", event_type, call_id)
        return {"ok": True}

    metadata = call.get("metadata") or {}
    share_link = (metadata.get("share_link") or "").strip()
    if not isinstance(metadata, dict):
        metadata = {}

    logger.warning(
        "🧾 CALL HEADER | event=%s call_id=%s metadata_keys=%s",
        event_type,
        call_id,
        list(metadata.keys()),
    )

    # -------------------------
    # Parse metadata
    # -------------------------
    vendor_call_ref = (metadata.get("vendor_call_ref") or "").strip()
    project_request_id = _to_int(metadata.get("project_request_id"))
    vendor_phone_norm = _norm_phone(
        metadata.get("vendor_phone")
        or metadata.get("dialed_phone")
        or metadata.get("to_number")
        or call.get("to_number")
    )

    raw_attachments = metadata.get("attachment_ids") or metadata.get("attachments") or []
    attachment_ids: list[int] = []
    if isinstance(raw_attachments, list):
        for x in raw_attachments:
            if isinstance(x, int):
                attachment_ids.append(x)
            elif isinstance(x, str) and x.strip().isdigit():
                attachment_ids.append(int(x.strip()))

    logger.warning(
        "🧩 META PARSED | call_id=%s project_request_id=%s vendor_phone_norm=%s vendor_call_ref=%s attachments=%s",
        call_id,
        project_request_id,
        vendor_phone_norm,
        vendor_call_ref,
        attachment_ids,
    )

    # -------------------------
    # Resolve VendorCall
    # -------------------------
    vendor_call: Optional[VendorCall] = None
    resolution_path = None

    if vendor_call_ref:
        ref_project_id, ref_phone = _parse_vendor_call_ref(vendor_call_ref)
        if ref_project_id and ref_phone:
            vendor_call = await _load_vendor_call_by_project_phone(db, ref_project_id, ref_phone)
            resolution_path = "vendor_call_ref"
        logger.warning(
            "🔎 vendor_call_ref lookup | call_id=%s ref_project_id=%s ref_phone=%s found=%s",
            call_id,
            ref_project_id,
            ref_phone,
            bool(vendor_call),
        )

    if not vendor_call and project_request_id and vendor_phone_norm:
        vendor_call = await _load_vendor_call_by_project_phone(db, project_request_id, vendor_phone_norm)
        if vendor_call:
            resolution_path = "project_request_id+vendor_phone"

    if not vendor_call:
        vendor_call = await _load_vendor_call_by_retell_call_id(db, call_id)
        if vendor_call:
            resolution_path = "retell_call_id"

    if not vendor_call and vendor_phone_norm:
        vendor_call = await _load_most_recent_by_phone(db, vendor_phone_norm)
        if vendor_call:
            resolution_path = "most_recent_by_phone"

    if not vendor_call:
        logger.error(
            "❌ VendorCall NOT FOUND | call_id=%s project_request_id=%s vendor_phone_norm=%s vendor_call_ref=%s",
            call_id,
            project_request_id,
            vendor_phone_norm,
            vendor_call_ref,
        )
        return {"ok": True}

    # Always link retell_call_id if missing
    if not vendor_call.retell_call_id:
        vendor_call.retell_call_id = call_id

    # Mark completed when either ended or analyzed (safe)
    if event_type in {"call_ended", "call_analyzed"}:
        vendor_call.status = "completed"

    # Persist attachments once per call_id
    if attachment_ids:
        existing = await db.execute(select(CallAttachments).where(CallAttachments.call_id == call_id))
        if not existing.scalar_one_or_none():
            db.add(CallAttachments(call_id=call_id, attachments=attachment_ids))
            logger.warning("📎 Attachments persisted | call_id=%s attachments=%s", call_id, attachment_ids)

    await db.commit()

    logger.warning(
        "✅ VendorCall RESOLVED | call_id=%s vendor_call_id=%s resolution_path=%s project_request_id=%s vendor_phone=%s",
        call_id,
        vendor_call.id,
        resolution_path,
        vendor_call.project_request_id,
        vendor_call.vendor_phone,
    )

    # -------------------------
    # Only attempt email send on call_analyzed
    # -------------------------
    if event_type != "call_analyzed":
        logger.info("ℹ️ Not analyzed yet, skipping email send | call_id=%s event=%s", call_id, event_type)
        return {"ok": True}

    email, email_confirmed = extract_email_and_confirmation(call)

    logger.warning(
        "🧠 ANALYSIS PARSED | call_id=%s email=%s confirmed=%s attachments=%s",
        call_id,
        email,
        email_confirmed,
        attachment_ids,
    )

    if not email:
        logger.error("❌ No email captured (after extractor) | call_id=%s", call_id)
        return {"ok": True}

    # For now do NOT block on confirmation (you can re-enable later)
    # if not email_confirmed:
    #     logger.warning("⚠️ Email not confirmed | call_id=%s email=%s", call_id, email)
    #     return {"ok": True}

    # Optional: attachments can be empty; email is still valid
    # If you want attachments required only in some scenarios, enforce inside send_vendor_email.

    # Dedupe: EmailLog is the real gatekeeper
    sent = await db.execute(
        select(EmailLog).where(
            EmailLog.related_call_id == call_id,
            EmailLog.email_type == "retell_vendor",
        )
    )
    if sent.scalar_one_or_none():
        logger.warning("🛑 Email already sent, skipping | call_id=%s", call_id)
        return {"ok": True}

    from app.routes.subcontractor_email import send_vendor_email

    logger.warning(
        "📤 SENDING EMAIL | call_id=%s vendor_call_id=%s project_request_id=%s email=%s attachments=%s",
        call_id,
        vendor_call.id,
        vendor_call.project_request_id,
        email,
        attachment_ids,
    )

    await send_vendor_email(
        payload={
            "vendor_email": email,
            "project_request_id": vendor_call.project_request_id,
            "attachments": attachment_ids,
            "subject": "Project Drawings – BAINS Development",
           "message": (
                "As discussed on the call, attached are the project files."
                + (f"\n\nLarge files link:\n{share_link}" if share_link else "")
            ),
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

    logger.warning("✅ EMAIL SENT | call_id=%s email=%s", call_id, email)
    return {"ok": True}