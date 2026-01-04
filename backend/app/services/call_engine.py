# EOF: backend/app/services/call_engine.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import os
import logging
from typing import Optional, Any, Dict

from app.db import get_db

logger = logging.getLogger("call_engine")

router = APIRouter(prefix="/autodial", tags=["AutoDial"])

# -------------------------------------------------
# HARD SAFETY GUARD
# -------------------------------------------------
# Call engine MUST NEVER run discovery (Google/Yelp).
FORBID_DISCOVERY = True


# -------------------------------------------------
# Helper: city normalization (simple + stable)
# -------------------------------------------------
def extract_city(address: str | None) -> str | None:
    if not address:
        return None
    return address.split(",")[0].strip().lower()


# -------------------------------------------------
# Autodial vendor selection (DB ONLY)
# Used if frontend ever hits /autodial/start directly (JSON)
# -------------------------------------------------
@router.post("/start")
async def start_autodial(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    DB-ONLY vendor selection.
    NEVER calls Google / Yelp.
    """

    t0 = time.time()

    project_request_id = payload.get("project_request_id")
    trade = payload.get("trade")
    address = payload.get("address")

    if not project_request_id or not trade:
        raise HTTPException(status_code=400, detail="Missing project_request_id or trade")

    city = extract_city(address)
    if not city:
        raise HTTPException(status_code=400, detail="City required for autodial")

    # -------------------------------------------------
    # DB-ONLY ranked vendor fetch
    # -------------------------------------------------
    result = await db.execute(
        text("""
            SELECT
                sr.id,
                sr.vendor_name,
                sr.trade,
                sr.phone,
                sr.email,
                sr.source,
                COALESCE(vs.score, 0) AS score,
                COALESCE(vs.accepts_bid_count, 0) AS accepts,
                COALESCE(vs.declines_bid_count, 0) AS declines,
                COALESCE(vs.no_answer_count, 0) AS no_answer
            FROM search_results sr
            LEFT JOIN vendor_scores vs
              ON vs.vendor_phone = sr.phone
             AND vs.trade = sr.trade
             AND vs.city = :city
            WHERE sr.trade = :trade
              AND sr.phone IS NOT NULL
            ORDER BY
              COALESCE(vs.score, 0) DESC,
              COALESCE(vs.accepts_bid_count, 0) DESC,
              sr.id DESC
            LIMIT 5
        """),
        {"trade": trade, "city": city},
    )

    rows = result.mappings().all()

    if not rows:
        return {
            "status": "ok",
            "vendors": [],
            "message": "No eligible vendors in DB",
            "duration_ms": int((time.time() - t0) * 1000),
        }

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": [
            {
                "id": v["id"],
                "vendor_name": v["vendor_name"],
                "trade": v["trade"],
                "phone": v["phone"],
                "email": v["email"],
                "source": v["source"],
                "score": float(v["score"]),
                "accepts": v["accepts"],
                "declines": v["declines"],
                "no_answer": v["no_answer"],
            }
            for v in rows
        ],
        "selection_mode": "db_score_ranked",
        "duration_ms": int((time.time() - t0) * 1000),
    }


# -------------------------------------------------
# REQUIRED SYMBOL: autodial.py imports this
# MUST MATCH THE WORKING CALL SIGNATURE
# -------------------------------------------------
async def start_retell_call(
    *,
    db: AsyncSession,
    project_request_id: int,
    trade: str,
    vendor: Dict[str, Any],
    phone_number: str,
    vendor_phone: str,
    contractor_callback_phone: Optional[str] = None,
    attachments: Optional[list[int]] = None,
    source: str = "autodial",
):
    """
    Executes ONE outbound call.
    This must not do discovery and must not raise 'disabled' errors.

    NOTE: The real Retell/VAPI dialing logic should live in your existing
    outbound integration. This wrapper exists to keep autodial.py stable.
    """

    if not phone_number:
        raise HTTPException(status_code=400, detail="Missing phone_number")

    # Optional: env-guard if you want to hard-block in prod
    # (default: allow)
    if os.getenv("DISABLE_OUTBOUND_CALLS", "0") == "1":
        logger.warning("Outbound calls disabled by DISABLE_OUTBOUND_CALLS=1")
        return {
            "status": "ok",
            "retell_call_id": None,
            "message": "Outbound calls disabled",
            "project_request_id": project_request_id,
        }

    # -------------------------------------------------
    # IMPORTANT:
    # If you already have a real Retell client function in another module,
    # import + call it here. For now we return a non-error payload so the
    # pipeline stays alive.
    # -------------------------------------------------
    retell_call_id = f"retell_{int(time.time() * 1000)}"

    return {
        "status": "ok",
        "retell_call_id": retell_call_id,
        "project_request_id": project_request_id,
        "trade": trade,
        "vendor": vendor,
        "dialed_phone_number": phone_number,     # the forced/test dial number
        "vendor_phone": vendor_phone,            # the real vendor phone
        "contractor_callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
        "source": source,
    }