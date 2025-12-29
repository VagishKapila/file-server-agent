from fastapi import APIRouter, Form, HTTPException, Depends
import json, os, requests, logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.vendor_call import VendorCall
from app.utils.call_guard import enforce_test_call

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


@router.post("/test")
async def autodial_test(
    vendors: str = Form(...),
    project_request_id: int = Form(...),
    trade: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell env vars")

    vendor_list = json.loads(vendors)
    vendor = vendor_list[0]

    vendor_phone = vendor.get("phone")
    vendor_name = vendor.get("name")

    # ---------- CREATE VENDOR CALL ----------
    vendor_call = VendorCall(
        project_request_id=project_request_id,
        trade=trade,
        vendor_name=vendor_name,
        vendor_phone=vendor_phone,
        status="called",
    )
    db.add(vendor_call)
    await db.flush()  # get vendor_call.id

    # ---------- TEST PHONE SAFETY ----------
    dialed_phone = enforce_test_call(vendor_phone)

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": dialed_phone,
        "metadata": {
            "project_request_id": project_request_id,
            "vendor_call_id": vendor_call.id,
            "trade": trade,
            "original_vendor_phone": vendor_phone,
            "source": "railway-retell-autodial",
        },
    }

    logger.warning("📞 RETELL CALL PAYLOAD: %s", payload)

    res = requests.post(
        RETELL_CALL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    res.raise_for_status()
    await db.commit()

    return {
        "status": "called",
        "vendor_call_id": vendor_call.id,
        "retell_response": res.json(),
    }