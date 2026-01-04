# EOF: backend/app/services/call_engine.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time

from app.db import get_db

router = APIRouter(prefix="/autodial", tags=["AutoDial"])

# -------------------------------------------------
# HARD SAFETY GUARD
# -------------------------------------------------
# Call engine MUST NEVER run discovery
FORBID_DISCOVERY = True


# -------------------------------------------------
# Helper: city normalization
# -------------------------------------------------
def extract_city(address: str | None) -> str | None:
    if not address:
        return None
    return address.split(",")[0].strip().lower()


# -------------------------------------------------
# Autodial request (DB ONLY)
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
        raise HTTPException(
            status_code=400,
            detail="Missing project_request_id or trade",
        )

    city = extract_city(address)
    if not city:
        raise HTTPException(
            status_code=400,
            detail="City required for autodial",
        )

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
        {
            "trade": trade,
            "city": city,
        },
    )

    vendors = result.mappings().all()

    if not vendors:
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
            for v in vendors
        ],
        "selection_mode": "db_score_ranked",
        "duration_ms": int((time.time() - t0) * 1000),
    }


# -------------------------------------------------
# REQUIRED SYMBOL (BOOT FIX)
# -------------------------------------------------
async def start_retell_call(*args, **kwargs):
    """
    Stub required by autodial.py import.
    Actual call execution intentionally disabled.
    """
    raise RuntimeError(
        "start_retell_call is disabled. "
        "Autodial execution is not active."
    )