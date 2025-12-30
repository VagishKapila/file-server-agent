# file-server/autodial.py
from fastapi import APIRouter, Form, HTTPException
import os, json, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

# ---------------- ENV ----------------
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL")  # https://backendaivagi-production.up.railway.app
TEST_PHONE_NUMBER = os.getenv("TEST_PHONE_NUMBER")  # optional: file-server side hard-lock (leave set for safety)

if not BACKEND_BASE_URL:
    raise RuntimeError("BACKEND_BASE_URL is not set")

BACKEND_RETELL_AUTODIAL_ENDPOINT = f"{BACKEND_BASE_URL.rstrip('/')}/autodial_vapi/start"


def _enforce_test_number(phone: str) -> str:
    """
    Optional safety: if TEST_PHONE_NUMBER is set on file-server,
    we force calls to that number. This is ONLY for dialing safety.
    We still send original vendor phone separately so backend can store it.
    """
    if TEST_PHONE_NUMBER and TEST_PHONE_NUMBER.strip():
        return TEST_PHONE_NUMBER.strip()
    return phone


@router.get("/__env_check")
def env_check():
    return {
        "BACKEND_BASE_URL": BACKEND_BASE_URL,
        "BACKEND_RETELL_AUTODIAL_ENDPOINT": BACKEND_RETELL_AUTODIAL_ENDPOINT,
        "TEST_PHONE_NUMBER_set": bool(TEST_PHONE_NUMBER),
    }


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    callback_phone: str = Form(...),
    vendors: str = Form(...),        # JSON list
    attachments: str = Form("[]"),   # JSON list of attachment IDs (numbers)
):
    """
    ✅ FILE-SERVER CANONICAL AUTODIAL (RETELL ONLY)
    - DO NOT call /autodial_vapi/start
    - Delegate to backend /autodial/start (Retell flow)
    - Ensure attachments are forwarded
    """

    # ---------------- Parse vendors ----------------
    try:
        vendor_list = json.loads(vendors)
        if not isinstance(vendor_list, list) or not vendor_list:
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    vendor = vendor_list[0]
    original_vendor_phone = vendor.get("phone") or vendor.get("phone_number")
    if not original_vendor_phone:
        raise HTTPException(status_code=400, detail="Vendor missing phone")

    # Dial safety (test lock)
    dialed_phone = _enforce_test_number(original_vendor_phone)

    # Keep vendor object but replace phone used for dialing
    vendor_for_dial = {**vendor, "phone": dialed_phone}

    # ---------------- Parse attachments ----------------
    try:
        attachment_ids = json.loads(attachments)
        if not isinstance(attachment_ids, list):
            attachment_ids = []
    except Exception:
        attachment_ids = []

    # ---------------- Send to BACKEND (RETELL) ----------------
    # Important: we send BOTH fields so backend code can read either name safely.
    backend_payload = {
        "project_request_id": int(project_request_id),
        "project_address": project_address,
        "trade": trade,
        "callback_phone": callback_phone,
        "vendors": json.dumps([vendor_for_dial]),
        # send both keys for compatibility
        "attachments": json.dumps(attachment_ids),
        "link_attachments": json.dumps(attachment_ids),
        # optional: preserve original vendor phone for backend to log/store
        "original_vendor_phone": original_vendor_phone,
    }

    logger.info("📤 File-server -> Backend RETELL autodial payload: %s", backend_payload)

    try:
        res = requests.post(
            BACKEND_RETELL_AUTODIAL_ENDPOINT,
            data=backend_payload,   # backend expects Form fields
            timeout=30,
        )
    except Exception as e:
        logger.error("❌ Backend autodial request failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Backend autodial request failed")

    logger.info("📥 Backend response | status=%s body=%s", res.status_code, res.text[:400])

    if res.status_code >= 400:
        raise HTTPException(status_code=500, detail=f"Backend autodial failed: {res.text}")

    return {"status": "ok", "backend_response": res.json()}