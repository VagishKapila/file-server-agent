import logging
import os
import requests
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError

from app.models.vendor_call import VendorCall

logger = logging.getLogger("retell-call-engine")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

RETELL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


async def start_retell_call(
    *,
    db: AsyncSession,
    project_request_id: int,
    trade: str,
    vendor: dict,
    phone_number: str,
    attachments: list | None = None,
    source: str = "autodial",
):
    """
    SINGLE source of truth for outbound Retell calls.
    DO NOT pass metadata from callers — enforced here.
    """

    # -------------------------
    # 0️⃣ Hard env guard
    # -------------------------
    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise RuntimeError("Retell environment variables not fully configured")

    # -------------------------
    # 1️⃣ Create VendorCall FIRST
    # -------------------------
    vc = VendorCall(
        project_request_id=project_request_id,
        trade=trade,
        vendor_name=vendor.get("name"),
        vendor_phone=phone_number,
        status="called",
    )

    try:
        db.add(vc)
        await db.flush()  # vc.id guaranteed
    except SQLAlchemyError:
        logger.exception("[RETELL CALL ENGINE] DB error creating VendorCall")
        raise

    logger.warning(
        "[RETELL CALL ENGINE] creating call",
        extra={
            "project_request_id": project_request_id,
            "vendor_call_id": vc.id,
            "vendor_name": vendor.get("name"),
            "phone": phone_number,
            "attachments": attachments or [],
            "source": source,
        },
    )

    # -------------------------
    # 2️⃣ Retell payload (ONLY here)
    # -------------------------
    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": phone_number,
        "metadata": {
            "vendor_call_id": vc.id,
            "project_request_id": project_request_id,
            "attachments": attachments or [],
            "source": source,
        },
    }

    try:
        res = requests.post(
            RETELL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        res.raise_for_status()
        retell_data = res.json()

    except requests.Timeout:
        logger.error(
            "[RETELL CALL ENGINE] timeout",
            extra={"vendor_call_id": vc.id, "phone": phone_number},
        )
        raise

    except requests.HTTPError:
        logger.error(
            "[RETELL CALL ENGINE] HTTP error",
            extra={
                "vendor_call_id": vc.id,
                "status_code": res.status_code,
                "response": res.text,
            },
        )
        raise

    except Exception:
        logger.exception("[RETELL CALL ENGINE] unexpected error calling Retell")
        raise

    # -------------------------
    # 3️⃣ Persist retell_call_id
    # -------------------------
    vc.retell_call_id = retell_data.get("call_id")

    try:
        await db.commit()
    except SQLAlchemyError:
        logger.exception(
            "[RETELL CALL ENGINE] DB commit failed after Retell success",
            extra={"vendor_call_id": vc.id},
        )
        raise

    logger.warning(
        "[RETELL CALL ENGINE] call started",
        extra={
            "vendor_call_id": vc.id,
            "retell_call_id": vc.retell_call_id,
        },
    )

    return {
        "vendor_call_id": vc.id,
        "retell_call_id": vc.retell_call_id,
    }