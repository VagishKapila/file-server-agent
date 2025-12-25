from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import logging
from datetime import datetime

router = APIRouter()

logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


@router.post("/retell/webhook")
async def retell_webhook(request: Request):
    """
    Retell Agent Webhook
    - Extracts post-call data
    - Confirms email capture
    - Triggers email sending logic
    """

    try:
        data = await request.json()
    except Exception as e:
        logger.error("❌ RETELL: Failed to parse JSON payload")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    logger.info("📞 RETELL WEBHOOK RECEIVED")
    logger.info(f"RAW PAYLOAD: {data}")

    # --------------------------------------------------
    # STEP A — IDENTIFY CALL + PROJECT CONTEXT
    # --------------------------------------------------

    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
        or data.get("call", {}).get("id")
    )

    # Project Request ID is OPTIONAL — Retell does NOT send it
    # We default safely instead of blocking email
    project_request_id = (
        data.get("metadata", {}).get("project_request_id")
        or data.get("call", {}).get("metadata", {}).get("project_request_id")
        or None
    )

    logger.info(
        f"📌 CONTEXT | call_id={call_id} | project_request_id={project_request_id}"
    )

    # --------------------------------------------------
    # STEP B — EXTRACT POST-CALL DATA (THE FIX)
    # --------------------------------------------------
    # Retell sends extracted fields here:
    # call.call_analysis.custom_analysis_data

    structured = (
        data.get("structured_output")
        or data.get("extracted_data")
        or data.get("conversation", {}).get("structured_output")
        or data.get("call", {})
            .get("call_analysis", {})
            .get("custom_analysis_data")
        or {}
    )

    logger.info(f"🧠 EXTRACTED DATA: {structured}")

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    # --------------------------------------------------
    # STEP C — VALIDATION (NO MORE BLOCKING)
    # --------------------------------------------------

    if not email or not email_confirmed:
        logger.warning(
            f"🟡 RETELL: Email not confirmed | email={email} | confirmed={email_confirmed}"
        )
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "email_not_confirmed"},
        )

    logger.info(
        f"✅ RETELL EMAIL CONFIRMED | email={email} | interest={interest}"
    )

    # --------------------------------------------------
    # STEP D — SEND EMAIL (PROJECT ID OPTIONAL)
    # --------------------------------------------------

    try:
        send_project_email(
            to_email=email,
            project_request_id=project_request_id,
            call_id=call_id,
        )

        logger.info(f"📩 EMAIL SENT SUCCESSFULLY → {email}")

    except Exception as e:
        logger.error(f"❌ EMAIL SEND FAILED → {email} | {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "email send failed"},
        )

    # --------------------------------------------------
    # STEP E — FINAL ACK
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


# --------------------------------------------------
# EMAIL SENDER (EXAMPLE / EXISTING)
# --------------------------------------------------

def send_project_email(to_email: str, project_request_id=None, call_id=None):
    """
    Your existing email logic goes here.
    DO NOT require project_request_id.
    """
    logger.info(
        f"📨 Sending email | to={to_email} | project_request_id={project_request_id} | call_id={call_id}"
    )

    # Example placeholder
    # email_service.send(...)
    return True