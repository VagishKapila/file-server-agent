# app/routes/autodial.py

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

    # ---- optional / guarded ----
    attachments: Optional[str] = Form("[]"),
    retell_metadata: Optional[str] = Form("{}"),
    debug: Optional[bool] = Form(False),

    db: AsyncSession = Depends(get_db),
):
    start_ts = time.time()

    # -------------------------
    # Guard: unexpected fields
    # -------------------------
    allowed_fields = {
        "project_request_id",
        "project_address",
        "trade",
        "max_confirmed",
        "vendors",
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

    # -------------------------
    # Parse vendors JSON
    # -------------------------
    try:
        vendor_list: List[Dict[str, Any]] = json.loads(vendors)
        if not isinstance(vendor_list, list):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    # -------------------------
    # Parse attachments
    # -------------------------
    try:
        raw_attachment_ids = json.loads(attachments or "[]")
        if not isinstance(raw_attachment_ids, list):
            raise ValueError

        attachment_ids: List[int] = []
        for x in raw_attachment_ids:
            try:
                attachment_ids.append(int(x))
            except Exception:
                continue

    except Exception:
        raise HTTPException(status_code=400, detail="Invalid attachments JSON")

    # -------------------------
    # Parse retell metadata
    # -------------------------
    try:
        meta = json.loads(retell_metadata or "{}")
        if not isinstance(meta, dict):
            raise ValueError
        retell_meta: Dict[str, Any] = meta
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid retell_metadata JSON")

    # -------------------------
    # AUTO-HYDRATE vendors if empty
    # -------------------------
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
                "[AUTODIAL DEBUG] vendors auto-hydrated",
                extra={
                    "project_request_id": project_request_id,
                    "vendor_count": len(vendor_list),
                },
            )

    # -------------------------
    # Debug snapshot
    # -------------------------
    if debug:
        logger.warning(
            "[AUTODIAL DEBUG] input snapshot",
            extra={
                "project_request_id": project_request_id,
                "project_address": project_address,
                "trade": trade,
                "max_confirmed": max_confirmed,
                "vendor_count": len(vendor_list),
                "attachments": attachment_ids,
            },
        )

    # -------------------------
    # Call loop
    # -------------------------
    calls_made = 0
    calls_log: List[Dict[str, Any]] = []

    for idx, vendor in enumerate(vendor_list):
        if calls_made >= max_confirmed:
            break

        if not isinstance(vendor, dict):
            continue

        phone = vendor.get("phone_e164") or vendor.get("phone")
        if not phone:
            continue

        try:
            result = await start_retell_call(
                db=db,
                project_request_id=project_request_id,
                trade=trade,
                vendor=vendor,
                phone_number=phone,
                attachments=attachment_ids,
                source="autodial",
            )

            calls_made += 1

            calls_log.append(
                {
                    "vendor": vendor.get("name"),
                    "vendor_call_id": result.get("vendor_call_id"),
                    "retell_call_id": result.get("retell_call_id"),
                    "status": "called",
                }
            )

        except Exception as e:
            logger.exception(
                "[AUTODIAL ERROR] start_retell_call failed",
                extra={
                    "project_request_id": project_request_id,
                    "vendor_index": idx,
                    "vendor_name": vendor.get("name"),
                    "phone": phone,
                },
            )

            calls_log.append(
                {
                    "vendor": vendor.get("name"),
                    "status": "error",
                    "error": str(e),
                }
            )

    duration_ms = int((time.time() - start_ts) * 1000)

    if debug:
        logger.warning(
            "[AUTODIAL DEBUG] completed",
            extra={
                "project_request_id": project_request_id,
                "calls_made": calls_made,
                "duration_ms": duration_ms,
            },
        )

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
        "duration_ms": duration_ms,
    }