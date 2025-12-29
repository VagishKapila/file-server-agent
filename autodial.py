# file-server/autodial.py
from fastapi import APIRouter, Form, HTTPException
import os, json, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")  # <- your number in Railway vars

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


def _enforce_test_number(vendor_phone: str) -> str:
    """
    Hard lock to TEST_PHONE_NUMBER if set.
    If not set, fall back to vendor phone (still works, but not recommended for prod).
    """
    if TEST_PHONE_NUMBER and TEST_PHONE_NUMBER.strip():
        return TEST_PHONE_NUMBER.strip()
    return vendor_phone


@router.get("/_retell_check")
def retell_check():
    return {
        "RETELL_API_KEY": bool(RETELL_API_KEY),
        "RETELL_AGENT_ID": bool(RETELL_AGENT_ID),
        "RETELL_PHONE_NUMBER": bool(RETELL_PHONE_NUMBER),
        "TEST_PHONE_NUMBER": bool(TEST_PHONE_NUMBER),
    }


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    callback_phone: str = Form(...),
    vendors: str = Form(...),  # JSON string list
    attachments: str = Form("[]"),  # keep for compatibility (links/ids)
):
    """
    ✅ RETELL DIALER (FILE-SERVER)
    - Accepts browser form-data
    - Forces calls to TEST_PHONE_NUMBER (your phone) if set
    - Puts everything needed into metadata for backend /retell/webhook
    """

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell env vars on file-server")

    try:
        vendor_list = json.loads(vendors)
        if not isinstance(vendor_list, list) or not vendor_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    try:
        att_list = json.loads(attachments)
        if not isinstance(att_list, list):
            att_list = []
    except Exception:
        att_list = []

    vendor = vendor_list[0]
    vendor_phone = vendor.get("phone") or vendor.get("phone_number")
    if not vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    dialed_phone = _enforce_test_number(vendor_phone)

    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": dialed_phone,
        "metadata": {
            # Core context
            "project_request_id": project_request_id,
            "project_address": project_address,
            "trade": trade,
            "callback_phone": callback_phone,

            # Vendor info
            "vendor_name": vendor.get("name"),
            "original_vendor_phone": vendor_phone,
            "dialed_phone": dialed_phone,

            # Attachments (links/ids) to be used by backend email sender
            "attachments": att_list,

            # Debug
            "source": "file-server-retell-autodial",
            "mode": "test" if (TEST_PHONE_NUMBER and dialed_phone == TEST_PHONE_NUMBER) else "live",
        },
    }

    logger.info("📞 RETELL CALL: dialing=%s original_vendor=%s", dialed_phone, vendor_phone)

    res = requests.post(
        RETELL_CALL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    logger.info("📞 RETELL STATUS=%s body=%s", res.status_code, res.text[:300])
    if res.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Retell call failed: {res.text}")

    return {
        "status": "ok",
        "dialed_phone": dialed_phone,
        "original_vendor_phone": vendor_phone,
        "retell": res.json(),
    }