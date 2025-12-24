from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import List
import json
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models.activity_log import ActivityLog
from backend.app.services.resolve_dial import resolve_dial_number
from backend.app.services.jessica_gateway import start_jessica_call

router = APIRouter(prefix="/autodial", tags=["autodial"])


@router.post("/start")
async def autodial_start(
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),              # JSON string list
    link_attachments: str = Form("[]"),    # JSON string list
    file_attachments: List[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Autodial entrypoint
    - resolves test vs real numbers
    - calls Jessica WAPI
    - logs everything
    """

    # -------------------------------
    # Parse vendors JSON
    # -------------------------------
    try:
        vendor_list = json.loads(vendors)
    except Exception:
        vendor_list = []

    # -------------------------------
    # Parse links JSON
    # -------------------------------
    try:
        link_list = json.loads(link_attachments)
    except Exception:
        link_list = []

    filenames = [f.filename for f in (file_attachments or [])]

    # -------------------------------
    # Log autodial start (summary)
    # -------------------------------
    db.add(ActivityLog(
        user_id="u1",
        project_id="p1",
        action="autodial_start",
        payload={
            "project_address": project_address,
            "trade": trade,
            "max_confirmed": max_confirmed,
            "vendors": vendor_list,
            "links": link_list,
            "files": filenames,
        },
    ))
    await db.commit()

    # -------------------------------
    # Call vendors via Jessica
    # -------------------------------
    call_results = []

    for vendor in vendor_list:
        phone = vendor.get("phone")
        if not phone:
            continue

        dial_number = await resolve_dial_number(
            real_number=phone,
            db=db
        )

        result = await start_jessica_call(
            phone_number=dial_number,
            vendor=vendor,
            project_address=project_address,
            trade=trade,
        )

        call_results.append(result)

    return {
        "status": "ok",
        "message": "Autodial started",
        "calls_started": len(call_results),
        "results": call_results,
    }