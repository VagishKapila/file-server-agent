# EOF: backend/app/routes/autodial.py

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
from app.utils.call_guard import enforce_test_call

logger = logging.getLogger("autodial")
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/autodial", tags=["autodial"])


@router.post("/start")
async def autodial_start(
    request: Request,

    project_request_id: int = Form(...),
    project_address: str = Form(...),
    trade: str = Form(...),
    max_confirmed: int = Form(...),
    vendors: str = Form(...),

    # contractor callback (metadata only)
    callback_phone: Optional[str] = Form(""),

    attachments: Optional[str] = Form("[]"),
    retell_metadata: Optional[str] = Form("{}"),
    debug: Optional[bool] = Form(False),

    db: AsyncSession = Depends(get_db),
):
    start_ts = time.time()

    logger.info("🚀 AUTODIAL START")
    logger.info(
        "INPUT project_request_id=%s trade=%s max_confirmed=%s callback_phone=%s",
        project_request_id,
        trade,
        max_confirmed,
        callback_phone,
    )

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
        logger.error("❌ Unexpected form fields: %s", sorted(unexpected))
        raise HTTPException(
            status_code=422,
            detail=f"Unexpected form fields: {sorted(unexpected)}",
        )

    # -----------------------
    # Parse vendors
    # -----------------------
    try:
        vendor_list: List[Dict[str, Any]] = json.loads(vendors)
        if not isinstance(vendor_list, list):
            raise ValueError
    except Exception as e:
        logger.error("❌ Invalid vendors JSON: %s | raw=%s", e, vendors)
        raise HTTPException(status_code=400, detail="Invalid vendors JSON")

    logger.info("📦 Vendors received: %d", len(vendor_list))
    if debug:
        logger.info("🧪 Vendors payload: %s", vendor_list)

    # -----------------------
    # Parse attachments
    # -----------------------
    try:
        attachment_ids = [int(x) for x in json.loads(attachments or "[]")]
    except Exception as e:
        logger.error("❌ Invalid attachments JSON: %s | raw=%s", e, attachments)
        raise HTTPException(status_code=400, detail="Invalid attachments JSON")

    logger.info("📎 Attachments parsed: %s", attachment_ids)

    # -----------------------
    # Fallback to DB search results
    # -----------------------
    if not vendor_list:
        logger.warning("⚠️ No vendors provided — falling back to SearchResult")
        result = await db.execute(
            select(SearchResult)
            .where(SearchResult.project_request_id == project_request_id)
            .limit(50)
        )
        vendor_list = [
            {
                "id": r.id,
                "name": r.vendor_name,
                "phone": r.phone,
                "trade": r.trade,
                "source": r.source,
            }
            for r in result.scalars().all()
            if r.phone
        ]
        logger.info("🔁 Vendors loaded from DB: %d", len(vendor_list))

    calls_made = 0
    calls_log: List[Dict[str, Any]] = []

    # -----------------------
    # Call loop
    # -----------------------
    for idx, vendor in enumerate(vendor_list):
        if calls_made >= max_confirmed:
            logger.info("🛑 Max confirmed reached (%s)", max_confirmed)
            break

        if not isinstance(vendor, dict):
            logger.warning("⚠️ Skipping non-dict vendor at index %s", idx)
            continue

        vendor_phone = vendor.get("phone")
        logger.info(
            "🔍 Vendor[%s] name=%s phone=%s",
            idx,
            vendor.get("name"),
            vendor_phone,
        )

        if not vendor_phone:
            logger.warning(
                "⏭️ Skipping vendor with NO phone | vendor=%s",
                vendor.get("name"),
            )
            continue

        # Force beta routing
        dial_number = enforce_test_call(vendor_phone)
        logger.info(
            "📞 Dialing vendor=%s real=%s dialed=%s",
            vendor.get("name"),
            vendor_phone,
            dial_number,
        )

        try:
            result = await start_retell_call(
                db=db,
                project_request_id=project_request_id,
                trade=trade,
                vendor=vendor,
                phone_number=dial_number,        # forced
                vendor_phone=vendor_phone,       # real vendor
                contractor_callback_phone=callback_phone,
                attachments=attachment_ids,
                source="autodial",
            )

            calls_made += 1
            calls_log.append({
                "vendor": vendor.get("name"),
                "vendor_phone": vendor_phone,
                "dialed": dial_number,
                "retell_call_id": result.get("retell_call_id"),
                "status": "called",
            })

            logger.info(
                "✅ Call placed | vendor=%s call_id=%s",
                vendor.get("name"),
                result.get("retell_call_id"),
            )

        except Exception as e:
            logger.exception(
                "❌ Call failed | vendor=%s phone=%s",
                vendor.get("name"),
                vendor_phone,
            )
            calls_log.append({
                "vendor": vendor.get("name"),
                "vendor_phone": vendor_phone,
                "status": "error",
                "error": str(e),
            })

    duration_ms = int((time.time() - start_ts) * 1000)
    logger.info(
        "🏁 AUTODIAL END | calls_made=%s duration_ms=%s",
        calls_made,
        duration_ms,
    )

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "calls_made": calls_made,
        "calls_log": calls_log,
        "duration_ms": duration_ms,
    }