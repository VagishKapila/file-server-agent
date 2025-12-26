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
    - Receives post-call payload
    - Reads structured extraction
    - Sends email directly (NO forwarding)
    """

    try:
        data = await request.json()
    except Exception:
        logger.error("❌ RETELL: Invalid JSON payload")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    # ---------------- DEBUG ----------------
    logger.info("🔴 RETELL RAW PAYLOAD 🔴")
    logger.info(data)

    # ---------------- CONTEXT ----------------
    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
    )

    project_request_id = (
        data.get("call", {})
        .get("metadata", {})
        .get("project_request_id")
    )

    logger.info(
        f"📌 CONTEXT | call_id={call_id} | project_request_id={project_request_id}"
    )

    # ---------------- STRUCTURED DATA ----------------
    structured = (
        data.get("call", {})
        .get("call_analysis", {})
        .get("custom_analysis_data", {})
    )

    logger.info(f"🧠 STRUCTURED DATA = {structured}")

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    # ---------------- VALIDATION ----------------
    if not email or not email_confirmed:
        logger.warning(
            f"🟡 Email not confirmed | email={email} | confirmed={email_confirmed}"
        )
        return JSONResponse(
            status_code=200,
            content={"status": "ignored", "reason": "email_not_confirmed"},
        )

    logger.info(f"✅ EMAIL CONFIRMED → {email}")

    # ---------------- SEND EMAIL ----------------
    try:
        send_project_email(
            to_email=email,
            project_request_id=project_request_id,
            call_id=call_id,
        )
        logger.info(f"📩 EMAIL SENT → {email}")

    except Exception as e:
        logger.error(f"❌ EMAIL SEND FAILED → {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": "email send failed"},
        )

    # ---------------- DONE ----------------
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
# EMAIL SENDER (YOUR REAL IMPLEMENTATION GOES HERE)
# --------------------------------------------------
def send_project_email(to_email: str, project_request_id=None, call_id=None):
    logger.info(
        f"📨 Sending email | to={to_email} | project_request_id={project_request_id} | call_id={call_id}"
    )

    # 🔥 CALL YOUR EXISTING EMAIL SERVICE HERE
    # email_service.send(...)

    return True
