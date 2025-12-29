from fastapi import APIRouter, Form, HTTPException
import json, os, requests, logging

from app.utils.call_guard import enforce_test_call

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


@router.post("/start")
async def autodial_start(
    vendors: str = Form(...),
):
    """
    🔒 TEST MODE SAFE
    - Vendors saved normally
    - Calls ONLY test phone
    """

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell env vars")

    try:
        vendor_list = json.loads(vendors)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    if not vendor_list:
        raise HTTPException(status_code=400, detail="No vendors provided")

    # Use FIRST vendor only for call trigger
    vendor = vendor_list[0]

    vendor_phone = vendor.get("phone")
    if not vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    # 🔒 FORCE TEST PHONE
    dialed_phone = enforce_test_call(vendor_phone)

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": dialed_phone,
        "metadata": {
            "source": "railway-test",
            "original_vendor_phone": vendor_phone,
        },
    }

    logger.warning(f"📞 CALLING (TEST MODE) {dialed_phone}")
    logger.warning(f"📞 PAYLOAD {payload}")

    res = requests.post(
        RETELL_CALL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    logger.warning(f"📞 RETELL STATUS {res.status_code}")
    logger.warning(f"📞 RETELL BODY {res.text}")

    res.raise_for_status()

    return {
        "status": "called",
        "dialed_phone": dialed_phone,
        "retell_response": res.json(),
    }