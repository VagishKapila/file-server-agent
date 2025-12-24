from fastapi import APIRouter, UploadFile, File, Form, Depends
from typing import List, Dict, Any
import json
import os

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..db import get_db
from ..models.activity_log import ActivityLog
from ..models.beta_subscriber import BetaSubscriber

from ..services.resolve_dial import resolve_dial_number
from backend.app.services.jessica_gateway import start_jessica_call

router = APIRouter(prefix="/autodial", tags=["autodial"])

BETA_MODE = os.getenv("BETA_MODE", "false").lower() == "true"


async def get_beta_vendors(db: AsyncSession):
    rows = await db.execute(
        select(BetaSubscriber)
        .where(BetaSubscriber.active == True)
        .limit(10)
    )
    beta = rows.scalars().all()

    if not beta:
        return None

    return [
        {
            "name": b.name or "Beta Sub",
            "phone": b.phone,
            "trade": b.trade,
            "email": b.email,
            "preferred": True,
        }
        for b in beta
    ]


@router.post("/start")
async def autodial_start(
    project_request_id: int = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),              # JSON string list
    link_attachments: str = Form("[]"),
    file_attachments: List[UploadFile] = File(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Autodial entrypoint
    - Supports BETA_MODE override
    - Routes calls through Jessica (VAPI)
    """

    # -------------------------------
    # Vendor source resolution
    # -------------------------------
    vendor_list: List[Dict[str, Any]] = []

    if BETA_MODE:
        beta_vendors = await get_beta_vendors(db)
        if beta_vendors:
            vendor_list = beta_vendors

    if not vendor_list:
        try:
            vendor_list = json.loads(vendors)
            if not isinstance(vendor_list, list):
                raise ValueError
        except Exception:
            vendor_list = []

    # -------------------------------
    # Parse links
    # -------------------------------
    try:
        link_list = json.loads(link_attachments)
        if not isinstance(link_list, list):
            raise ValueError
    except Exception:
        link_list = []

    filenames = [f.filename for f in (file_attachments or [])]

    calls_log: List[Dict[str, Any]] = []
    calls_made = 0

    # -------------------------------
    # Call loop
    # -------------------------------
    for vendor in vendor_list:
        if calls_made >= max_confirmed:
            break

        if not isinstance(vendor, dict):
            continue

        real_number = vendor.get("phone") or vendor.get("phone_number")
        if not real_number:
            continue

        try:
            dial_number = await resolve_dial_number(
                real_number=real_number,
                db=db,
            )

            vapi_result = await start_jessica_call(
                phone_number=dial_number,
                vendor=vendor,
                project_address=project_address,
                trade=trade,
                project_request_id=project_request_id,
                db=db,
            )

            calls_made += 1

            db.add(
                ActivityLog(
                    user_id="u1",  # TODO: real user later
                    project_id=str(project_request_id),
                    action="jessica_call_started",
                    payload={
                        "vendor": vendor.get("name"),
                        "real_number": real_number,
                        "dialed_number": dial_number,
                        "trade": trade,
                        "project_address": project_address,
                        "project_request_id": project_request_id,
                        "vapi_result": vapi_result,
                    },
                )
            )
            await db.commit()

            calls_log.append(
                {
                    "vendor": vendor,
                    "dialed_number": dial_number,
                    "status": "ok",
                }
            )

        except Exception as e:
            calls_log.append(
                {
                    "vendor": vendor,
                    "real_number": real_number,
                    "status": "error",
                    "error": str(e),
                }
            )

    # -------------------------------
    # Master activity log
    # -------------------------------
    db.add(
        ActivityLog(
            user_id="u1",
            project_id=str(project_request_id),
            action="autodial_start",
            payload={
                "project_request_id": project_request_id,
                "project_address": project_address,
                "trade": trade,
                "max_confirmed": max_confirmed,
                "vendors": vendor_list,
                "links": link_list,
                "files": filenames,
                "calls_made": calls_made,
                "calls_log": calls_log,
                "beta_mode": BETA_MODE,
            },
        )
    )
    await db.commit()

    return {
        "status": "ok",
        "beta_mode": BETA_MODE,
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
    }