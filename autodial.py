# file-server/autodial.py
from fastapi import APIRouter, Form, HTTPException
import os, json, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL")  # e.g. https://backendaivagi-production.up.railway.app

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


def _enforce_test_number(vendor_phone: str) -> str:
    if TEST_PHONE_NUMBER and TEST_PHONE_NUMBER.strip():
        return TEST_PHONE_NUMBER.strip()
    return vendor_phone


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    callback_phone: str = Form(...),
    vendors: str = Form(...),
    attachments: str = Form("[]"),
):
    """
    CANONICAL RETELL AUTODIAL (Option A1)
    - Creates VendorCall via backend
    - Injects vendor_call_id into Retell metadata
    """

    if not all([RETELL_API_KEY, RETELL_AGENT_ID, RETELL_PHONE_NUMBER, BACKEND_BASE_URL]):
        raise HTTPException(status_code=500, detail="Missing required environment variables")

    # -------------------------
    # Parse vendors
    # -------------------------
    try:
        vendor_list = json.loads(vendors)
        if not vendor_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    vendor = vendor_list[0]
    vendor_phone = vendor.get("phone") or vendor.get("phone_number")
    vendor_name = vendor.get("name")

    if not vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    dialed_phone = _enforce_test_number(vendor_phone)

    try:
        att_list = json.loads(attachments)
        if not isinstance(att_list, list):
            att_list = []
    except Exception:
        att_list = []

    # -------------------------
    # STEP 1: CREATE VENDOR CALL (BACKEND)
    # -------------------------
    vc_res = requests.post(
        f"{BACKEND_BASE_URL}/vendor-calls/create",
        json={
            "project_request_id": project_request_id,
            "trade": trade,
            "vendor_name": vendor_name,
            "vendor_phone": vendor_phone,
            "status": "called",
        },
        timeout=20,
    )

    if vc_res.status_code != 200:
        logger.error("❌ VendorCall create failed: %s", vc_res.text)
        raise HTTPException(status_code=500, detail="Failed to create VendorCall")

    vendor_call_id = vc_res.json().get("vendor_call_id")

    if not vendor_call_id:
        raise HTTPException(status_code=500, detail="vendor_call_id missing from backend")

    logger.info("✅ VendorCall created | id=%s", vendor_call_id)

    # -------------------------
    # STEP 2: CALL RETELL
    # -------------------------
    payload = {
        "override_agent_id": RETELL_AGENT_ID,
        "from_number": RETELL_PHONE_NUMBER,
        "to_number": dialed_phone,
        "metadata": {
            "vendor_call_id": vendor_call_id,          # 🔑 CRITICAL
            "project_request_id": project_request_id,
            "project_address": project_address,
            "trade": trade,
            "callback_phone": callback_phone,

            "vendor_name": vendor_name,
            "original_vendor_phone": vendor_phone,
            "dialed_phone": dialed_phone,

            "attachments": att_list,

            "source": "file-server-retell-autodial",
            "mode": "test" if dialed_phone == TEST_PHONE_NUMBER else "live",
        },
    }

    logger.info("📞 RETELL PAYLOAD: %s", payload)

    res = requests.post(
        RETELL_CALL_ENDPOINT,
        headers={
            "Authorization": f"Bearer {RETELL_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if res.status_code >= 400:
        logger.error("❌ Retell call failed: %s", res.text)
        raise HTTPException(status_code=500, detail="Retell call failed")

    logger.info("🔥 RETELL CALL STARTED | vendor_call_id=%s", vendor_call_id)

    return {
        "status": "ok",
        "vendor_call_id": vendor_call_id,
        "dialed_phone": dialed_phone,
        "retell": res.json(),
    }