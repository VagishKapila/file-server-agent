from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import os
import requests
import logging

router = APIRouter()

logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


@router.post("/retell/webhook")
async def retell_webhook(request: Request):
    """
    Retell Agent Webhook
    - Extracts post-call data
    - Confirms email capture
    - Forwards payload to backend
    """

    try:
        data = await request.json()
    except Exception:
        logger.error("❌ RETELL: Failed to parse JSON payload")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    # --------------------------------------------------
    # DEBUG
    # --------------------------------------------------
    logger.info("🔴 FULL RAW PAYLOAD 🔴")
    logger.info(data)

    logger.info("🔴 TOP LEVEL KEYS 🔴")
    for k in data.keys():
        logger.info(f"KEY: {k}")

    # --------------------------------------------------
    # STEP A — CONTEXT
    # --------------------------------------------------
    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
        or data.get("call", {}).get("id")
    )

    project_request_id = (
        data.get("metadata", {}).get("project_request_id")
        or data.get("call", {}).get("metadata", {}).get("project_request_id")
        or None
    )

    logger.info(
        f"📌 CONTEXT | call_id={call_id} | project_request_id={project_request_id}"
    )

    # --------------------------------------------------
    # STEP B — EXTRACT STRUCTURED DATA (RETELL-SAFE)
    # --------------------------------------------------
    structured = {}

    paths = [
        data.get("structured_output"),
        data.get("extracted_data"),
        data.get("post_call", {}).get("extracted_data"),
        data.get("analysis", {}).get("custom_analysis_data"),
        data.get("analysis", {}).get("structured_data"),
        data.get("call", {}).get("analysis", {}).get("custom_analysis_data"),
        data.get("call", {}).get("analysis", {}).get("structured_data"),
        data.get("call", {}).get("call_analysis", {}).get("custom_analysis_data"),
    ]

    for p in paths:
        if isinstance(p, dict) and p:
            structured = p
            break

    logger.info(f"🧠 FINAL STRUCTURED DATA USED: {structured}")

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    # --------------------------------------------------
    # STEP C — VALIDATION
    # --------------------------------------------------
    if not email or not email_confirmed:
        logger.warning(
            f"🟡 RETELL: Email not confirmed | email={email} | confirmed={email_confirmed}"
        )
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "email_not_confirmed"},
        )

    logger.info(f"✅ RETELL EMAIL CONFIRMED | email={email} | interest={interest}")

    # --------------------------------------------------
    # STEP D — FORWARD TO BACKEND (NO INDENT BUG)
    # --------------------------------------------------
    BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL")

    if not BACKEND_BASE_URL:
        logger.error("❌ BACKEND_BASE_URL IS NOT SET")
        return JSONResponse(
            status_code=500,
            content={"detail": "BACKEND_BASE_URL not configured"},
        )

    try:
        r = requests.post(
            f"{BACKEND_BASE_URL}/retell/webhook",
            json=data,
            timeout=10,
        )
    except Exception as e:
        logger.error(f"❌ BACKEND REQUEST FAILED | {str(e)}")
        return JSONResponse(
            status_code=502,
            content={"detail": "Backend request failed"},
        )

    logger.info(
        f"➡️ BACKEND RESPONSE | status={r.status_code} | body={r.text}"
    )

    if r.status_code >= 300:
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Backend webhook failed",
                "backend_status": r.status_code,
                "backend_response": r.text,
            },
        )

    # --------------------------------------------------
    # FINAL ACK
    # --------------------------------------------------
    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "email": email,
            "call_id": call_id,
            "project_request_id": project_request_id,
        },
    )