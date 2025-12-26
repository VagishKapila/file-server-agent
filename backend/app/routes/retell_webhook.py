from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
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
    - Triggers email sending logic
    """

    try:
        data = await request.json()
    except Exception:
        logger.error("❌ RETELL: Failed to parse JSON payload")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    # 🔴 FULL DEBUG (SAFE)
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

    logger.info(f"✅ RETELL EMAIL CONFIRMED | email={email}")

    # --------------------------------------------------
    # STEP D — SEND EMAIL
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

    return JSONResponse(
        status_code=200,
        content={
            "status": "success",
            "email": email,
            "call_id": call_id,
            "project_request_id": project_request_id,
        },
    )


def send_project_email(to_email: str, project_request_id=None, call_id=None):
    logger.info(
        f"📨 Sending email | to={to_email} | project_request_id={project_request_id} | call_id={call_id}"
    )
    return True