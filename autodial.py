from fastapi import APIRouter, Form, HTTPException
import os, json, requests, logging

router = APIRouter(prefix="/autodial", tags=["autodial"])
logger = logging.getLogger("autodial")

BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL")
if not BACKEND_BASE_URL:
    raise RuntimeError("BACKEND_BASE_URL not set")


@router.post("/start")
async def autodial_start(
    project_request_id: str = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    vendors: str = Form(...),
    callback_phone: str = Form(...),
):
    """
    File-server relay → backend autodial (Jessica / VAPI)
    """

    try:
        json.loads(vendors)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    logger.info("➡️ Relaying autodial to backend VAPI")

    r = requests.post(
        f"{BACKEND_BASE_URL}/autodial_vapi/start",
        data={
            "project_request_id": project_request_id,
            "project_address": project_address,
            "trade": trade,
            "vendors": vendors,
            "callback_phone": callback_phone,
            "max_confirmed": 3,
        },
        timeout=30,
    )

    if r.status_code >= 400:
        logger.error("❌ Backend autodial failed: %s", r.text)
        raise HTTPException(status_code=500, detail="Backend autodial failed")

    return r.json()