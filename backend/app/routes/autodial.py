from fastapi import APIRouter, Form, Depends, HTTPException, Request
from typing import List, Dict, Any, Optional
import json
import logging
import time

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.services.call_engine import start_retell_call
from app.models.search_result import SearchResult

logger = logging.getLogger("autodial")

router = APIRouter(prefix="/autodial", tags=["autodial"])


@router.post("/start")
async def autodial_start(
    request: Request,

    # ---- strict contract ----
    project_request_id: int = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),

    # ---- NEW (critical) ----
    callback_phone: Optional[str] = Form(None),

    # ---- optional / guarded ----
    attachments: Optional[str] = Form("[]"),
    retell_metadata: Optional[str] = Form("{}"),
    debug: Optional[bool] = Form(False),

    db: AsyncSession = Depends(get_db),
):
    start_ts = time.time()

    allowed_fields = {
        "project_request_id",
        "project_address",
        "trade",
        "max_confirmed",
        "vendors",
        "callback_phone",
        "attachments",
        "retell_metadata",
        "debug",
    }

    form = await request.form()
    unexpected = set(form.keys()) - allowed_fields
    if unexpected:
        raise HTTPException(
            status_code=422,
            detail=f"Unexpected form fields: {sorted(unexpected)}",
        )

    try:
        vendor_list: List[Dict[str, Any]] = json.loads(vendors)
        if not isinstance(vendor_list, list):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    try:
        attachment_ids = [int(x) for x in json.loads(attachments or "[]")]
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid attachments JSON")

    if not vendor_list:
        result = await db.execute(
            select(SearchResult)
            .where(SearchResult.project_request_id == project_request_id)
            .limit(25)
        )

        vendor_list = [
            {
                "name": r.vendor_name,
                "phone": r.phone,
                "trade": r.trade,
                "source": r.source,
            }
            for r in result.scalars().all()
            if r.phone
        ]

    if debug:
        logger.warning(
            "[AUTODIAL DEBUG] input snapshot",
            extra={
                "project_request_id": project_request_id,
                "vendor_count": len(vendor_list),
                "callback_phone": callback_phone,
            },
        )

    calls_made = 0
    calls_log: List[Dict[str, Any]] = []

    for idx, vendor in enumerate(vendor_list):
        if calls_made >= max_confirmed:
            break

        phone_to_call = callback_phone or vendor.get("phone_e164") or vendor.get("phone")
        if not phone_to_call:
            continue

        try:
            result = await start_retell_call(
                db=db,
                project_request_id=project_request_id,
                trade=trade,
                vendor=vendor,
                phone_number=phone_to_call,
                attachments=attachment_ids,
                source="autodial",
            )

            calls_made += 1

            calls_log.append(
                {
                    "vendor": vendor.get("name"),
                    "dialed": phone_to_call,
                    "retell_call_id": result.get("retell_call_id"),
                    "status": "called",
                }
            )

        except Exception as e:
            logger.exception("[AUTODIAL ERROR]")
            calls_log.append(
                {
                    "vendor": vendor.get("name"),
                    "status": "error",
                    "error": str(e),
                }
            )

    duration_ms = int((time.time() - start_ts) * 1000)

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
        "duration_ms": duration_ms,
    }