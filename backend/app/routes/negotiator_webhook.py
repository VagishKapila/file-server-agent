# EOF: backend/app/routes/negotiator_webhook.py

from fastapi import APIRouter, Request, Depends
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.db import get_db
from app.models.vendor_call import VendorCall

router = APIRouter(prefix="/negotiator", tags=["negotiator"])
logger = logging.getLogger("negotiator-webhook")
logger.setLevel(logging.INFO)


def _to_int(v) -> Optional[int]:
    try:
        if v is None or isinstance(v, bool):
            return None
        return int(str(v).strip())
    except Exception:
        return None


@router.post("/webhook")
async def negotiator_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    logger.info("📥 NEGOTIATOR RAW PAYLOAD: %s", payload)

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
    # Status mapping
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

    if not new_status:
        logger.info(
            "ℹ️ Negotiator event ignored | vendor_call_id=%s event=%s",
            vendor_call_id,
            event_type,
        )
        return {"ok": True}

    vendor_call.status = new_status
    await db.commit()

    logger.info(
        "🔄 VendorCall updated | vendor_call_id=%s status=%s",
        vendor_call_id,
        new_status,
    )

    # -------------------------------------------------
    # ✅ VENDOR SCORING (SAFE UPSERT)
    # -------------------------------------------------
    score_sql = None

    if new_status == "confirmed":
        score_sql = """
        INSERT INTO public.vendor_scores (
            vendor_phone,
            vendor_name,
            trade,
            city,
            accepts_bid_count,
            score
        )
        VALUES (
            :vendor_phone,
            :vendor_name,
            :trade,
            :city,
            1,
            3
        )
        ON CONFLICT (vendor_phone, trade, city)
        DO UPDATE SET
            accepts_bid_count = vendor_scores.accepts_bid_count + 1,
            score = vendor_scores.score + 3,
            updated_at = NOW();
        """

    elif new_status == "declined":
        score_sql = """
        INSERT INTO public.vendor_scores (
            vendor_phone,
            vendor_name,
            trade,
            city,
            declines_bid_count,
            score
        )
        VALUES (
            :vendor_phone,
            :vendor_name,
            :trade,
            :city,
            1,
            -1
        )
        ON CONFLICT (vendor_phone, trade, city)
        DO UPDATE SET
            declines_bid_count = vendor_scores.declines_bid_count + 1,
            score = vendor_scores.score - 1,
            updated_at = NOW();
        """

    elif new_status == "no_answer":
        score_sql = """
        INSERT INTO public.vendor_scores (
            vendor_phone,
            vendor_name,
            trade,
            city,
            no_answer_count,
            score
        )
        VALUES (
            :vendor_phone,
            :vendor_name,
            :trade,
            :city,
            1,
            -0.5
        )
        ON CONFLICT (vendor_phone, trade, city)
        DO UPDATE SET
            no_answer_count = vendor_scores.no_answer_count + 1,
            score = vendor_scores.score - 0.5,
            updated_at = NOW();
        """

    if score_sql:
        await db.execute(
            text(score_sql),
            {
                "vendor_phone": vendor_call.vendor_phone,
                "vendor_name": vendor_call.vendor_name,
                "trade": vendor_call.trade,
                "city": (vendor_call.city or "").lower(),
            },
        )
        await db.commit()

        logger.info(
            "📊 Vendor score updated | phone=%s trade=%s city=%s status=%s",
            vendor_call.vendor_phone,
            vendor_call.trade,
            vendor_call.city,
            new_status,
        )

    return {"ok": True}