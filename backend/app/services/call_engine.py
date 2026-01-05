# EOF: backend/app/services/call_engine.py

import os
import time
import logging
import httpx
from typing import Optional, Dict, Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("call_engine")
logger.setLevel(logging.INFO)

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_FROM_NUMBER = os.getenv("RETELL_PHONE_NUMBER")  # matches Railway

RETELL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


# -------------------------------------------------
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
    REAL outbound Retell call.
    This is the missing piece.
    """

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_FROM_NUMBER:
        raise HTTPException(
            status_code=500,
            detail="Retell environment variables not configured",
        )

    if not phone_number:
        raise HTTPException(status_code=400, detail="Missing phone_number")

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_FROM_NUMBER,
        "to_number": phone_number,
        "metadata": {
            "source": source,
            "project_request_id": project_request_id,
            "vendor_phone": vendor_phone,
            "contractor_callback_phone": contractor_callback_phone,
            "attachments": attachments or [],
        },
    }

    logger.info("📞 RETELL OUTBOUND PAYLOAD: %s", payload)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            RETELL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if resp.status_code >= 300:
        logger.error("❌ Retell error %s | %s", resp.status_code, resp.text)
        raise HTTPException(
            status_code=500,
            detail=f"Retell call failed: {resp.text}",
        )

    data = resp.json()
    call_id = data.get("call_id")

    logger.info("✅ RETELL CALL PLACED | call_id=%s", call_id)

    return {
        "status": "ok",
        "retell_call_id": call_id,
        "project_request_id": project_request_id,
        "trade": trade,
        "vendor": vendor,
        "dialed_phone_number": phone_number,
        "vendor_phone": vendor_phone,
        "contractor_callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
        "source": source,
    }