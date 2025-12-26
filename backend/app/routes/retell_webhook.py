from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
import requests
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    logger.info("📞 RETELL WEBHOOK RECEIVED")
    logger.info(data)

    # ----------------------------
    # CONTEXT
    # ----------------------------
    call = data.get("call", {})

    call_id = call.get("call_id")
    project_request_id = call.get("metadata", {}).get("project_request_id")

    structured = (
        call.get("call_analysis", {})
            .get("custom_analysis_data", {})
    )

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True

    if not email or not email_confirmed:
        logger.warning("🟡 Email not confirmed")
        return {"ok": True}

    logger.info(f"✅ EMAIL CONFIRMED → {email}")

    # ----------------------------
    # SEND EMAIL VIA WORKING PIPE
    # ----------------------------
    try:
        payload = {
            "vendor_email": email,
            "project_request_id": project_request_id,
            "subject": "Project Drawings & Photos",
            "message": "Please see the attached drawings and photos."
        }

        # LOCAL call – same backend
        from app.routes.vendor_email import send_vendor_email
        await send_vendor_email(payload=payload, db=db)

        logger.info(f"📩 EMAIL SENT → {email}")

    except Exception as e:
        logger.error(f"❌ EMAIL FAILED → {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "email_send_failed"},
        )

    return {
        "status": "success",
        "email": email,
        "call_id": call_id,
        "project_request_id": project_request_id,
    }