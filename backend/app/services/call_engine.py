# EOF: backend/app/services/call_engine.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import os
import logging
import requests
from typing import Optional, Any, Dict

from app.db import get_db

logger = logging.getLogger("call_engine")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/autodial", tags=["AutoDial"])

# -------------------------------------------------
# HARD SAFETY GUARD
# -------------------------------------------------
FORBID_DISCOVERY = True

# -------------------------------------------------
# ENV REQUIRED
# -------------------------------------------------
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_FROM_NUMBER = os.getenv("RETELL_FROM_NUMBER")

if not RETELL_API_KEY:
    logger.warning("⚠️ RETELL_API_KEY not set")
if not RETELL_AGENT_ID:
    logger.warning("⚠️ RETELL_AGENT_ID not set")
if not RETELL_FROM_NUMBER:
    logger.warning("⚠️ RETELL_FROM_NUMBER not set")


# -------------------------------------------------
# Helper: city normalization
# -------------------------------------------------
def extract_city(address: str | None) -> str | None:
    if not address:
        return None
    return address.split(",")[0].strip().lower()


# -------------------------------------------------
# DB-ONLY autodial selection (unchanged)
# -------------------------------------------------
@router.post("/start")
async def start_autodial(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    project_request_id = payload.get("project_request_id")
    trade = payload.get("trade")
    address = payload.get("address")

    if not project_request_id or not trade:
        raise HTTPException(status_code=400, detail="Missing project_request_id or trade")

    city = extract_city(address)
    if not city:
        raise HTTPException(status_code=400, detail="City required for autodial")

    result = await db.execute(
        text("""
            SELECT
                sr.id,
                sr.vendor_name,
                sr.trade,
                sr.phone,
                sr.email,
                sr.source
            FROM search_results sr
            WHERE sr.trade = :trade
              AND sr.phone IS NOT NULL
            ORDER BY sr.id DESC
            LIMIT 5
        """),
        {"trade": trade},
    )

    rows = result.mappings().all()

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": rows,
        "duration_ms": int((time.time() - t0) * 1000),
    }


# -------------------------------------------------
# 🔥 THIS IS THE CRITICAL FUNCTION 🔥
# REQUIRED SYMBOL — autodial.py imports this
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
    Places ONE outbound Retell call WITH FULL METADATA.
    This is what fixes your issue.
    """

    if not phone_number:
        raise HTTPException(status_code=400, detail="Missing phone_number")

    if os.getenv("DISABLE_OUTBOUND_CALLS", "0") == "1":
        logger.warning("🚫 Outbound calls disabled by env")
        return {
            "status": "disabled",
            "retell_call_id": None,
        }

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_FROM_NUMBER:
        raise HTTPException(
            status_code=500,
            detail="Retell environment variables not configured",
        )

    # -------------------------------------------------
    # 🔑 METADATA — THIS WAS MISSING BEFORE
    # -------------------------------------------------
    metadata = {
        "source": source,
        "project_request_id": str(project_request_id),
        "trade": trade,
        "vendor_phone": vendor_phone,
        "vendor_name": vendor.get("name") or vendor.get("vendor_name"),
        "callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
    }

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_FROM_NUMBER,
        "to_number": phone_number,
        "metadata": metadata,
    }

    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json",
    }

    logger.info("📞 RETELL OUTBOUND CALL")
    logger.info("→ to_number=%s", phone_number)
    logger.info("→ metadata=%s", metadata)

    try:
        resp = requests.post(
            "https://api.retellai.com/v2/create-phone-call",
            json=payload,
            headers=headers,
            timeout=10,
        )
    except Exception as e:
        logger.exception("❌ Retell request failed")
        raise HTTPException(status_code=502, detail=str(e))

    if resp.status_code >= 300:
        logger.error("❌ Retell error %s | %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=502,
            detail=f"Retell error {resp.status_code}",
        )

    data = resp.json()
    retell_call_id = data.get("call_id")

    logger.info("✅ RETELL CALL CREATED | call_id=%s", retell_call_id)

    return {
        "status": "ok",
        "retell_call_id": retell_call_id,
        "project_request_id": project_request_id,
        "vendor_phone": vendor_phone,
        "dialed_phone_number": phone_number,
        "metadata": metadata,
    }