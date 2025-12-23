from fastapi import APIRouter, Form, HTTPException
import json, os, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    vendors: str = Form(...),
    callback_phone: str = Form(...),
    attachments: str = Form("[]"),
):
    # ✅ READ ENV AT RUNTIME (NOT IMPORT TIME)
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

    results = []

    for v in vendor_list:
        phone = v.get("phone")
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
                "callback_phone": callback_phone,
                "attachment_ids": attachment_ids,
            },
        }

        logger.info("Calling vendor=%s phone=%s attachments=%s", v.get("name"), phone, attachment_ids)

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
