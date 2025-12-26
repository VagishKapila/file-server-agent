from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.activity_log import ActivityLog
from app.models.email_log import EmailLog
from app.models.project_files import ProjectFile
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
    Retell Agent Webhook (FINAL, WORKING)
    - Reads structured output from Retell
    - Confirms email
    - Sends real email using unified_email_service
    """

    # --------------------------------------------------
    # STEP 0 — PARSE PAYLOAD
    # --------------------------------------------------
    try:
        data = await request.json()
    except Exception:
        logger.error("❌ RETELL: Failed to parse JSON payload")
        return JSONResponse(status_code=400, content={"error": "invalid json"})

    logger.info("🔥 RETELL RAW PAYLOAD")
    logger.info(data)

    # --------------------------------------------------
    # STEP A — CONTEXT
    # --------------------------------------------------
    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
    )

    project_request_id = (
        data.get("metadata", {}).get("project_request_id")
        or data.get("call", {}).get("metadata", {}).get("project_request_id")
    )

    logger.info(
        f"📌 CONTEXT | call_id={call_id} | project_request_id={project_request_id}"
    )

    # --------------------------------------------------
    # STEP B — STRUCTURED DATA (RETELL STANDARD)
    # --------------------------------------------------
    structured = (
        data.get("call", {})
            .get("call_analysis", {})
            .get("custom_analysis_data", {})
    )

    logger.info(f"🧠 STRUCTURED DATA: {structured}")

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

    logger.info(f"✅ EMAIL CONFIRMED → {email}")

    # --------------------------------------------------
    # STEP D — LOAD ATTACHMENTS (WORKING LOGIC)
    # --------------------------------------------------
    attachments = []

    if project_request_id:
        files = await db.execute(
            ProjectFile.__table__.select().where(
                ProjectFile.project_request_id == project_request_id
            )
        )

        for f in files.fetchall():
            if f.stored_path and os.path.exists(f.stored_path):
                attachments.append({
                    "path": f.stored_path,
                    "name": f.filename,
                    "type": f.file_type,
                })

    logger.info(f"📎 ATTACHMENTS FOUND: {len(attachments)}")

    # --------------------------------------------------
    # STEP E — SEND REAL EMAIL (THIS WAS WORKING)
    # --------------------------------------------------
    send_project_email(
        to_email=email,
        subject="Project Drawings & Photos",
        body="Please see the attached drawings and photos.",
        attachments=attachments,
    )

    logger.info(f"📩 EMAIL SENT SUCCESSFULLY → {email}")

    # --------------------------------------------------
    # STEP F — LOG ACTIVITY
    # --------------------------------------------------
    db.add(
        EmailLog(
            project_request_id=project_request_id,
            recipient_email=email,
            email_type="subcontractor",
            related_call_id=call_id,
        )
    )

    db.add(
        ActivityLog(
            user_id="system",
            project_id=str(project_request_id),
            action="retell_email_sent",
            payload={
                "email": email,
                "call_id": call_id,
                "interest": interest,
            },
        )
    )

    await db.commit()

    # --------------------------------------------------
    # STEP G — ACK
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