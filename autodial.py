# file-server/autodial.py

from fastapi import APIRouter, Form, HTTPException
import os, json, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

# ---------------- ENV ----------------
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL")  # https://backendaivagi-production.up.railway.app
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")

if not BACKEND_BASE_URL:
    raise RuntimeError("BACKEND_BASE_URL is not set")

# ---------------- HELPERS ----------------
def _enforce_test_number(phone: str) -> str:
    if TEST_PHONE_NUMBER and TEST_PHONE_NUMBER.strip():
        return TEST_PHONE_NUMBER.strip()
    return phone


# ---------------- ROUTE ----------------
@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    callback_phone: str = Form(...),
    vendors: str = Form(...),        # JSON list
    attachments: str = Form("[]"),   # JSON list of attachment IDs
):
    """
    ✅ CANONICAL AUTODIAL (FINAL)
    - File-server delegates EVERYTHING to backend
    - Backend creates VendorCall
    - Backend injects vendor_call_id
    - Retell webhook sends email + attachments
    """

    # ---------------- Parse vendors ----------------
    try:
        vendor_list = json.loads(vendors)
        if not isinstance(vendor_list, list) or not vendor_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    vendor = vendor_list[0]
    vendor_phone = vendor.get("phone") or vendor.get("phone_number")

    if not vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    vendor_phone = _enforce_test_number(vendor_phone)

    # ---------------- Parse attachments ----------------
    try:
        attachment_ids = json.loads(attachments)
        if not isinstance(attachment_ids, list):
            attachment_ids = []
    except Exception:
        attachment_ids = []

    # ---------------- CALL BACKEND (THE ONLY PLACE THAT DIALS) ----------------
    backend_payload = {
        "project_request_id": int(project_request_id),
        "project_address": project_address,
        "trade": trade,
        "max_confirmed": 1,
        "vendors": json.dumps([
            {
                **vendor,
                "phone": vendor_phone,
            }
        ]),
        "link_attachments": json.dumps(attachment_ids),
    }

    logger.info("📤 Sending autodial to backend: %s", backend_payload)

    res = requests.post(
        f"{BACKEND_BASE_URL}/autodial_vapi/start",
        data=backend_payload,
        timeout=30,
    )

    if res.status_code >= 400:
        logger.error("❌ Backend autodial failed: %s", res.text)
        raise HTTPException(status_code=500, detail="Backend autodial failed")

    logger.info("🔥 Autodial accepted by backend")

    return {
        "status": "ok",
        "backend_response": res.json(),
    }