# EOF: backend/app/services/call_engine.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import os
import logging
from typing import Optional, Any, Dict

import httpx

logger = logging.getLogger("call_engine")
logger.setLevel(logging.INFO)


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Retell environment variables not configured: missing {name}")
    return v


async def start_retell_call(
    *,
    db: AsyncSession,
    project_request_id: int,
    trade: str,
    vendor: Dict[str, Any],
    phone_number: str,                 # the actual number we will dial (your number during beta)
    vendor_phone: str,                 # the real vendor phone (stored + sent as metadata)
    contractor_callback_phone: Optional[str] = None,
    attachments: Optional[list[int]] = None,
    source: str = "autodial",
):
    if not phone_number:
        raise ValueError("Missing phone_number")

    # -------------------------------------------------
    # 0) REQUIRED ENV (fail loud)
    # -------------------------------------------------
    retell_api_key = _env("RETELL_API_KEY")
    retell_agent_id = _env("RETELL_AGENT_ID")
    retell_from_number = _env("RETELL_PHONE_NUMBER")  # must be E.164

    # -------------------------------------------------
    # 1) CREATE vendor_calls ROW FIRST (so webhook can resolve)
    # -------------------------------------------------
    result = await db.execute(
        text("""
            INSERT INTO public.vendor_calls (
                project_request_id,
                vendor_name,
                vendor_phone,
                trade,
                source,
                callback_phone,
                status,
                created_at
            )
            VALUES (
                :project_request_id,
                :vendor_name,
                :vendor_phone,
                :trade,
                :source,
                :callback_phone,
                'initiated',
                NOW()
            )
            RETURNING id
        """),
        {
            "project_request_id": project_request_id,
            "vendor_name": vendor.get("name") or vendor.get("vendor_name") or "",
            "vendor_phone": vendor_phone,
            "trade": trade,
            "source": source,
            "callback_phone": contractor_callback_phone,
        },
    )

    vendor_call_id = result.scalar_one()
    await db.commit()

    logger.info(
        "📞 VendorCall registered | id=%s vendor=%s vendor_phone=%s dial=%s",
        vendor_call_id,
        vendor.get("name") or vendor.get("vendor_name"),
        vendor_phone,
        phone_number,
    )

    # -------------------------------------------------
    # 2) CALL RETELL (REAL)
    # -------------------------------------------------
    retell_metadata = {
        "project_request_id": project_request_id,
        "vendor_phone": vendor_phone,
        "vendor_call_ref": str(vendor_call_id),   # webhook lookup key
        "contractor_callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
        "source": source,
    }

    payload = {
        "override_agent_id": retell_agent_id,
        "from_number": retell_from_number,
        "to_number": phone_number,
        "metadata": retell_metadata,
    }

    logger.info("🚀 Retell create-phone-call | vendor_call_id=%s", vendor_call_id)

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            "https://api.retellai.com/v2/create-phone-call",
            headers={
                "Authorization": f"Bearer {retell_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if r.status_code >= 300:
        logger.error("❌ Retell API error | status=%s body=%s", r.status_code, r.text)
        raise RuntimeError(f"Retell API error {r.status_code}: {r.text}")

    data = r.json()
    retell_call_id = data.get("call_id")

    if not retell_call_id:
        logger.error("❌ Retell missing call_id | body=%s", data)
        raise RuntimeError("Retell API did not return call_id")

    # -------------------------------------------------
    # 3) UPDATE vendor_calls with retell_call_id
    # -------------------------------------------------
    await db.execute(
        text("""
            UPDATE public.vendor_calls
            SET retell_call_id = :retell_call_id
            WHERE id = :vendor_call_id
        """),
        {"retell_call_id": retell_call_id, "vendor_call_id": vendor_call_id},
    )
    await db.commit()

    logger.info("✅ Retell call created | vendor_call_id=%s retell_call_id=%s", vendor_call_id, retell_call_id)

    return {
        "status": "ok",
        "retell_call_id": retell_call_id,
        "vendor_call_id": vendor_call_id,
        "dialed_phone_number": phone_number,
        "metadata": retell_metadata,
    }