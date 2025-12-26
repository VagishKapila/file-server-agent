from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
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
    try:
        data = await request.json()
    except Exception:
        logger.error("❌ Invalid JSON")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    logger.info("📞 RETELL WEBHOOK RECEIVED")
    logger.info(data)

    # -------------------------------
    # CONTEXT
    # -------------------------------
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
        f"📌 call_id={call_id} | project_request_id={project_request_id}"
    )

    # -------------------------------
    # STRUCTURED OUTPUT (RETELL)
    # -------------------------------
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

    logger.info(f"🧠 STRUCTURED DATA: {structured}")

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True

    if not email or not email_confirmed:
        logger.warning("🟡 Email not confirmed")
        return {"ok": True}

    if project_request_id is None:
        logger.error("❌ project_request_id missing — cannot attach files")
        return {"ok": True}

    # -------------------------------
    # SEND EMAIL (THIS IS THE ONLY ACTION)
    # -------------------------------
    try:
        send_project_email(
            to_email=email,
            project_request_id=project_request_id,
            call_id=call_id,
        )
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
        "project_request_id": project_request_id,
    }