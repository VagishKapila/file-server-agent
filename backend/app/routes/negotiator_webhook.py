from fastapi import APIRouter, Request, Depends
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.vendor_call import VendorCall

router = APIRouter(prefix="/negotiator", tags=["negotiator"])
logger = logging.getLogger("negotiator-webhook")


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


@router.post("/webhook")
async def negotiator_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()

    logger.warning("📥 NEGOTIATOR RAW PAYLOAD: %s", payload)

    event_type = payload.get("event") or payload.get("type")
    data = payload.get("data") or {}

    vendor_call_id = _to_int(
        data.get("vendor_call_id")
        or payload.get("vendor_call_id")
        or payload.get("call_ref")
    )

    if not vendor_call_id:
        logger.error("❌ Missing vendor_call_id | payload=%s", payload)
        return {"ok": True}

    res = await db.execute(
        select(VendorCall).where(VendorCall.id == vendor_call_id)
    )
    vendor_call = res.scalar_one_or_none()

    if not vendor_call:
        logger.error(
            "❌ VendorCall not found | vendor_call_id=%s event=%s",
            vendor_call_id,
            event_type,
        )
        return {"ok": True}

    # -------------------------
    # Status mapping (SAFE + SIMPLE)
    # -------------------------
    status_map = {
        "vendor_interested": "confirmed",
        "vendor_confirmed": "confirmed",
        "vendor_declined": "declined",
        "vendor_no_answer": "no_answer",
        "vendor_failed": "failed",
        "completed": "completed",
    }

    new_status = status_map.get(event_type)

    if new_status:
        vendor_call.status = new_status
        logger.warning(
            "🔄 VendorCall updated | vendor_call_id=%s status=%s",
            vendor_call_id,
            new_status,
        )
        await db.commit()
    else:
        logger.info(
            "ℹ️ Negotiator event ignored | vendor_call_id=%s event=%s",
            vendor_call_id,
            event_type,
        )

    return {"ok": True}