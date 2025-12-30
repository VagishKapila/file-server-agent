from fastapi import APIRouter, Form, Depends, HTTPException
from typing import List, Dict, Any
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.call_engine import start_retell_call

router = APIRouter(prefix="/autodial", tags=["autodial"])


@router.post("/start")
async def autodial_start(
    project_request_id: int = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),   # JSON list
    db: AsyncSession = Depends(get_db),
):
    try:
        vendor_list: List[Dict[str, Any]] = json.loads(vendors)
        assert isinstance(vendor_list, list)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    calls_made = 0
    calls_log = []

    for vendor in vendor_list:
        if calls_made >= max_confirmed:
            break

        phone = vendor.get("phone_e164")
        if not phone:
            continue

        result = await start_retell_call(
            db=db,
            project_request_id=project_request_id,
            trade=trade,
            vendor=vendor,
            phone_number=phone,
            source="autodial",
        )

        calls_made += 1

        calls_log.append(
            {
                "vendor": vendor.get("name"),
                "vendor_call_id": result["vendor_call_id"],
                "retell_call_id": result["retell_call_id"],
                "status": "called",
            }
        )

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
    }