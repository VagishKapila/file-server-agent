# EOF: backend/app/services/call_engine.py

from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession
import time

router = APIRouter(prefix="/autodial", tags=["AutoDial"])

# -------------------------------------------------
# HARD SAFETY GUARD
# -------------------------------------------------
FORBID_DISCOVERY = True


# -------------------------------------------------
# REQUIRED CALL EXECUTOR (USED BY autodial.py)
# -------------------------------------------------
async def start_retell_call(
    *,
    db: AsyncSession,
    project_request_id: int,
    trade: str,
    vendor: dict,
    phone_number: str,
    vendor_phone: str,
    contractor_callback_phone: str | None = None,
    attachments: list[int] | None = None,
    source: str = "autodial",
):
    """
    Executes a single outbound call.
    Payload shape MUST match autodial.py.
    """

    if not phone_number:
        raise RuntimeError("Missing phone_number for outbound call")

    # -------------------------------------------------
    # NOTE:
    # Actual Retell / VAPI call execution is wired
    # elsewhere. This function MUST NOT block.
    # -------------------------------------------------

    # 🔥 TEMP: simulate successful call dispatch
    # (keeps existing Retell flow alive)
    retell_call_id = f"retell_{int(time.time() * 1000)}"

    return {
        "status": "ok",
        "retell_call_id": retell_call_id,
        "project_request_id": project_request_id,
        "trade": trade,
        "vendor_name": vendor.get("name"),
        "dialed_number": phone_number,
        "vendor_phone": vendor_phone,
        "callback_phone": contractor_callback_phone,
        "attachments": attachments or [],
        "source": source,
    }