from fastapi import APIRouter, Form, HTTPException
import json, os, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


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
        status["agent_response"] = r.json() if r.status_code == 200 else r.text
    except Exception as e:
        return {"ok": False, "stage": "agent_fetch", "error": str(e), "status": status}

    return {"ok": True, "status": status}


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    vendors: str = Form(...),
    callback_phone: str = Form(...),
    attachments: str = Form("[]"),
):
    # 🔑 Read env at runtime
    RETELL_API_KEY = os.getenv("RETELL_API_KEY")
    RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
    RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell environment variables")

    # Parse attachment IDs
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

    # 🔒 HARD LIMIT — 5 vendors per batch
    vendor_list = vendor_list[:5]

    results = []

    for v in vendor_list:
        phone = v.get("phone")  # ✅ CALL VENDOR, NOT CALLBACK
        if not phone:
            continue

        payload = {
            "override_agent_id": RETELL_AGENT_ID,
            "from_number": RETELL_PHONE_NUMBER,
            "to_number": phone,
            "metadata": {
                "project_request_id": project_request_id,
                "project_address": project_address,
                "trade": trade,
                "vendor": v.get("name"),
                "callback_phone": callback_phone,  # ✅ metadata only
                "attachment_ids": attachment_ids,
            },
        }

        logger.info(
            "Calling vendor=%s phone=%s attachments=%s",
            v.get("name"),
            phone,
            attachment_ids,
        )

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

        results.append({
            "vendor": v.get("name"),
            "phone": phone,
            "call_id": data.get("call_id"),
        })

    return {"status": "ok", "calls": results}
