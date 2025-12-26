from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])

logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    STANDARD Retell webhook handler

    - Reads structured output from Retell
    - Confirms email
    - Sends email via unified_email_service
    - NO forwarding
    """

    try:
        data = await request.json()
    except Exception:
        logger.error("❌ RETELL: Invalid JSON")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    logger.info("📞 RETELL WEBHOOK RECEIVED")
    logger.info(data)

    # --------------------------------------------------
    # CONTEXT
    # --------------------------------------------------

    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
        or data.get("call", {}).get("id")
    )

    project_request_id = (
        data.get("metadata", {}).get("project_request_id")
        or data.get("call", {}).get("metadata", {}).get("project_request_id")
    )

    logger.info(
        f"📌 CONTEXT | call_id={call_id} | project_request_id={project_request_id}"
    )

    # --------------------------------------------------
    # STRUCTURED OUTPUT (RETELL STANDARD)
    # --------------------------------------------------

    structured = {}

    possible_paths = [
        data.get("structured_output"),
        data.get("extracted_data"),
        data.get("post_call", {}).get("extracted_data"),
        data.get("analysis", {}).get("custom_analysis_data"),
        data.get("call", {}).get("analysis", {}).get("custom_analysis_data"),
        data.get("call", {}).get("call_analysis", {}).get("custom_analysis_data"),
    ]

    for p in possible_paths:
        if isinstance(p, dict) and p:
            structured = p
            break

    logger.info(f"🧠 STRUCTURED DATA USED: {structured}")

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    if not email or not email_confirmed:
        logger.warning(
            f"🟡 EMAIL NOT CONFIRMED | email={email} | confirmed={email_confirmed}"
        )
        return {"ok": True}

    logger.info(f"✅ EMAIL CONFIRMED → {email}")

    # --------------------------------------------------
    # SEND EMAIL (THIS WAS WORKING BEFORE — REUSED)
    # --------------------------------------------------

    try:
        send_project_email(
            to_email=email,
            project_request_id=project_request_id,
            call_id=call_id,
        )
        logger.info(f"📩 EMAIL SENT → {email}")

    except Exception as e:
        logger.error(f"❌ EMAIL FAILED → {email} | {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "email_send_failed"},
        )

    return {
        "status": "success",
        "email": email,
        "call_id": call_id,
        "project_request_id": project_request_id,
        "interest": interest,
    }