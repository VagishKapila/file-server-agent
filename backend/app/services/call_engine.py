# EOF: backend/app/services/call_engine.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import os
import logging
from typing import Optional, Any, Dict

logger = logging.getLogger("call_engine")
logger.setLevel(logging.INFO)


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
    if not phone_number:
        raise ValueError("Missing phone_number")

    # -------------------------------------------------
    # 1️⃣ CREATE vendor_calls ROW FIRST
    # -------------------------------------------------
    result = await db.execute(
        text("""
            INSERT INTO vendor_calls (
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
            "vendor_name": vendor.get("name"),
            "vendor_phone": vendor_phone,
            "trade": trade,
            "source": source,
            "callback_phone": contractor_callback_phone,
        },
    )

    vendor_call_id = result.scalar_one()
    await db.commit()

    logger.info(
        "📞 VendorCall registered | id=%s vendor=%s phone=%s",
        vendor_call_id,
        vendor.get("name"),
        vendor_phone,
    )

    # -------------------------------------------------
    # 2️⃣ CALL RETELL
    # -------------------------------------------------
    retell_call_id = f"call_{int(time.time() * 1000)}"

    # IMPORTANT: this metadata is what the webhook resolves
    retell_metadata = {
        "project_request_id": project_request_id,
        "vendor_phone": vendor_phone,
        "vendor_call_ref": str(vendor_call_id),
        "contractor_callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
        "source": source,
    }

    logger.info(
        "🚀 Dialing via Retell | vendor_call_id=%s dial=%s",
        vendor_call_id,
        phone_number,
    )

    # 👉 Replace this block with your actual Retell client call
    # Example:
    # retell_call_id = retell_client.create_call(..., metadata=retell_metadata)

    return {
        "status": "ok",
        "retell_call_id": retell_call_id,
        "vendor_call_id": vendor_call_id,
        "dialed_phone_number": phone_number,
        "metadata": retell_metadata,
    }