from fastapi import APIRouter, Form, HTTPException, Depends
import json, os, requests, logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.call_attachments import CallAttachments

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

RETELL_API_KEY = os.getenv("RETELL_API_KEY")
RETELL_AGENT_ID = os.getenv("RETELL_AGENT_ID")
RETELL_PHONE_NUMBER = os.getenv("RETELL_PHONE_NUMBER")

RETELL_CALL_ENDPOINT = "https://api.retellai.com/v2/create-phone-call"


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    vendors: str = Form(...),
    callback_phone: str = Form(...),
    attachments: str = Form("[]"),  # JSON list of project_file IDs
    db: AsyncSession = Depends(get_db),
):
    if not RETELL_API_KEY or not RETELL_AGENT_ID or not RETELL_PHONE_NUMBER:
        raise HTTPException(status_code=500, detail="Missing Retell env")

    try:
        attachment_ids = json.loads(attachments)
    except Exception:
        attachment_ids = []

    vendor_list = json.loads(vendors)
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
                "trade": trade,
                "vendor": v.get("name"),
                "callback_phone": callback_phone,
                "attachment_ids": attachment_ids,  # 🔑 ONLY IDs
            },
        }

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
        call_id = data.get("call_id")

        # 🔒 HARD BACKUP — DB SOURCE OF TRUTH
        if call_id and attachment_ids:
            db.add(
            CallAttachments(
                call_id=call_id,
                attachments=attachment_ids,   # ✅ CORRECT
            )
        )
            await db.commit()

        results.append({
            "vendor": v.get("name"),
            "phone": phone,
            "call_id": call_id,
        })

    return {"status": "ok", "calls": results}