from fastapi import APIRouter, Form, HTTPException
import json
import os
import logging
import requests

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

# ---------------- ENV ----------------
RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

# 🔒 HARD TEST LOCK (YOU)
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER", "+14084106151")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


@router.post("/test")
async def autodial_test(
    vendors: str = Form(...),
):
    """
    🔒 RETELL TEST MODE (FILE-SERVER)
    - Accepts vendor list
    - ALWAYS calls TEST_PHONE_NUMBER
    - Preserves real vendor phone in metadata
    """

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell env vars")

    try:
        vendor_list = json.loads(vendors)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    if not vendor_list:
        raise HTTPException(status_code=400, detail="No vendors provided")

    vendor = vendor_list[0]

    vendor_phone = vendor.get("phone")
    if not vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    # 🔒 FORCE CALL TO YOU ONLY
    dialed_phone = TEST_PHONE_NUMBER

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": dialed_phone,
        "metadata": {
            "mode": "test",
            "source": "railway-file-server",
            "original_vendor_phone": vendor_phone,
            "tester_phone": dialed_phone,
        },
    }

    logger.warning("📞 RETELL TEST CALL INITIATED")
    logger.warning(f"📞 DIALING (LOCKED): {dialed_phone}")
    logger.warning(f"📞 REAL_VENDOR_PHONE: {vendor_phone}")
    logger.warning(f"📞 PAYLOAD: {payload}")

    try:
        res = requests.post(
            RETELL_CALL_ENDPOINT,
            headers={
                "Authorization": f"Bearer {RETELL_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
    except Exception as e:
        logger.exception("❌ Retell request failed")
        raise HTTPException(status_code=500, detail=str(e))

    logger.warning(f"📞 RETELL STATUS: {res.status_code}")
    logger.warning(f"📞 RETELL RESPONSE: {res.text}")

    res.raise_for_status()

    return {
        "status": "called",
        "mode": "test",
        "dialed_phone": dialed_phone,
        "real_vendor_phone": vendor_phone,
        "retell_response": res.json(),
    }