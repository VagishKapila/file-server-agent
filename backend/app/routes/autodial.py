from fastapi import APIRouter, Form, Depends
from typing import List, Dict, Any
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.vendor_call import VendorCall
from app.models.activity_log import ActivityLog
from app.services.resolve_dial import resolve_dial_number
from app.services.call_engine import start_retell_call  # ✅ RETELL ONLY

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/autodial", tags=["autodial"])


@router.post("/start")
async def autodial_start(
    project_request_id: int = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),  # JSON list
    db: AsyncSession = Depends(get_db),
):
    """
    Autodial entrypoint (RETELL ONLY)
    """

    try:
        vendor_list: List[Dict[str, Any]] = json.loads(vendors)
        if not isinstance(vendor_list, list):
            raise ValueError
    except Exception:
        return {"error": "Invalid vendors payload"}

    calls_made = 0
    calls_log = []

    for vendor in vendor_list:
        if calls_made >= max_confirmed:
            break

        phone = vendor.get("phone") or vendor.get("phone_e164")
        name = vendor.get("name")

        if not phone:
            continue

        # ----------------------------------------
        # 🔒 CREATE VendorCall FIRST (CRITICAL)
        # ----------------------------------------
        vendor_call = VendorCall(
            project_request_id=project_request_id,
            trade=trade,
            vendor_name=name,
            vendor_phone=phone,
            status="called",
        )
        db.add(vendor_call)
        await db.flush()  # ensures vendor_call.id exists

        try:
            dial_number = await resolve_dial_number(
                real_number=phone,
                db=db,
            )

            # ----------------------------------------
            # 🔒 START RETELL CALL (NO JESSICA)
            # ----------------------------------------
            retell_response = await start_retell_call(
                phone_number=dial_number,
                metadata={
                    "project_request_id": project_request_id,
                    "vendor_call_id": vendor_call.id,  # 🔑 invariant
                },
            )

            vendor_call.retell_call_id = retell_response.get("call_id")
            await db.commit()

            calls_made += 1

            db.add(
                ActivityLog(
                    user_id="system",
                    project_id=str(project_request_id),
                    action="retell_call_started",
                    payload={
                        "vendor_call_id": vendor_call.id,
                        "vendor": name,
                        "phone": phone,
                        "retell_call_id": vendor_call.retell_call_id,
                    },
                )
            )
            await db.commit()

            calls_log.append(
                {
                    "vendor": name,
                    "status": "called",
                    "vendor_call_id": vendor_call.id,
                }
            )

        except Exception as e:
            vendor_call.status = "failed"
            await db.commit()

            calls_log.append(
                {
                    "vendor": name,
                    "status": "error",
                    "error": str(e),
                }
            )

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
    }