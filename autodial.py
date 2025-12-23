from fastapi import APIRouter, Form, HTTPException
import json, os, requests, logging
import time

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


# =====================================================
# TEST / PROD DIAL RESOLUTION
# =====================================================
def resolve_to_number(vendor_phone: str, callback_phone: str) -> str:
    """
    PROD:
        → Calls vendor_phone

    TEST MODE:
        → Routes calls to one of AUTODIAL_TEST_NUMBERS
        → Real vendor phone is preserved in metadata
    """
    test_mode = os.getenv("AUTODIAL_TEST_MODE", "").lower() in ("1", "true", "yes")
    test_numbers_raw = os.getenv("AUTODIAL_TEST_TO_NUMBER", "")

    if not test_mode:
        return vendor_phone

    test_numbers = [n.strip() for n in test_numbers_raw.split(",") if n.strip()]

    # fallback to callback phone if list is empty
    if not test_numbers:
        return callback_phone

    # stable round-robin by vendor phone hash
    idx = abs(hash(vendor_phone or "")) % len(test_numbers)
    return test_numbers[idx]


# =====================================================
# HEALTH / RETELL CHECK
# =====================================================
@router.get("/_retell_check")
async def retell_check():
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
    RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
    RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

    status = {
        "RETELL_API_KEY": bool(RETELL_API_KEY),
        "RETELL_AGENT_ID": bool(RETELL_AGENT_ID),
        "RETELL_PHONE_NUMBER": bool(RETELL_PHONE_NUMBER),
        "raw_phone": RETELL_PHONE_NUMBER,
        "AUTODIAL_TEST_MODE": os.getenv("AUTODIAL_TEST_MODE"),
        "AUTODIAL_TEST_NUMBERS": os.getenv("AUTODIAL_TEST_NUMBERS"),
    }

    if not all([RETELL_API_KEY, RETELL_AGENT_ID, RETELL_PHONE_NUMBER]):
        return {"ok": False, "stage": "env", "status": status}

    try:
        r = requests.get(
            f"https://api.retellai.com/v1/agents/{RETELL_AGENT_ID}",
            headers={"Authorization": f"Bearer {RETELL_API_KEY}"},
            timeout=15,
        )
        status["agent_http_status"] = r.status_code
    except Exception as e:
        return {"ok": False, "stage": "agent_fetch", "error": str(e), "status": status}

    return {"ok": True, "status": status}


# =====================================================
# AUTODIAL START
# =====================================================
@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    vendors: str = Form(...),
    callback_phone: str = Form(...),
    attachments: str = Form("[]"),
):
    # Read env at runtime (Railway safe)
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
    RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
    RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell environment variables")

    # Parse attachments
    try:
        attachment_ids = json.loads(attachments)
        if not isinstance(attachment_ids, list):
            attachment_ids = []
    except Exception:
        attachment_ids = []

    # Parse vendors
    try:
        vendor_list = json.loads(vendors)
        if not isinstance(vendor_list, list):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors payload")

    results = []

    for v in vendor_list:
        vendor_phone = v.get("phone")
        if not vendor_phone:
            continue

        dial_phone = resolve_to_number(vendor_phone, callback_phone)

        payload = {
            "override_agent_id": RETELL_AGENT_ID,
            "from_number": RETELL_PHONE_NUMBER,
            "to_number": dial_phone,
            "metadata": {
                "project_request_id": project_request_id,
                "project_address": project_address,
                "trade": trade,
                "vendor": v.get("name"),
                "vendor_phone": vendor_phone,   # ✅ REAL vendor phone
                "dialed_phone": dial_phone,     # ✅ Who was actually called
                "callback_phone": callback_phone,
                "attachment_ids": attachment_ids,
            },
        }

        logger.info(
            "Calling vendor=%s vendor_phone=%s dialed_phone=%s attachments=%s",
            v.get("name"),
            vendor_phone,
            dial_phone,
            attachment_ids,
        )

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
            res.raise_for_status()
            data = res.json()
        except Exception as e:
            logger.error("❌ Retell call failed vendor=%s error=%s", v.get("name"), e)
            continue

        results.append({
            "vendor": v.get("name"),
            "vendor_phone": vendor_phone,
            "dialed_phone": dial_phone,
            "call_id": data.get("call_id"),
        })

        # small delay to avoid burst limits
        time.sleep(0.5)

    return {"status": "ok", "calls": results}
