# app/routes/retell_webhook.py
# NOTE: This file is for the BACKEND service (backendaivagi), not the relay.

from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])

logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


def _extract_structured(data: dict) -> dict:
    """
    Retell structured output can appear in different places depending on config.
    We scan known paths and return the first dict found.
    """
    candidates = [
        data.get("structured_output"),
        data.get("extracted_data"),
        data.get("post_call", {}).get("extracted_data"),
        data.get("analysis", {}).get("custom_analysis_data"),
        data.get("analysis", {}).get("structured_data"),
        data.get("call", {}).get("analysis", {}).get("custom_analysis_data"),
        data.get("call", {}).get("analysis", {}).get("structured_data"),
        data.get("call", {}).get("call_analysis", {}).get("custom_analysis_data"),
        data.get("call", {}).get("call_analysis", {}).get("structured_data"),
    ]
    for c in candidates:
        if isinstance(c, dict) and c:
            return c
    return {}


@router.post("/webhook")
async def retell_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    try:
        data = await request.json()
    except Exception:
        logger.exception("❌ Invalid JSON")
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    # Minimal safe debug
    logger.info("📞 RETELL WEBHOOK RECEIVED | keys=%s", list(data.keys()))

    # -------------------------------
    # CONTEXT
    # -------------------------------
    call_id = (
        data.get("call_id")
        or data.get("call", {}).get("call_id")
        or data.get("call", {}).get("id")
        or "unknown_call"
    )

    project_request_id = (
        data.get("metadata", {}).get("project_request_id")
        or data.get("call", {}).get("metadata", {}).get("project_request_id")
    )

    structured = _extract_structured(data)

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    logger.info(
        "📌 CONTEXT | call_id=%s | project_request_id=%s | email=%s | confirmed=%s",
        call_id,
        project_request_id,
        email,
        email_confirmed,
    )

    if not email or not email_confirmed:
        # Retell will retry depending on its settings; we return ok=True to stop spam retries
        return {"ok": True, "reason": "email_not_confirmed"}

    # -------------------------------
    # LOAD ATTACHMENTS (OPTIONAL)
    # -------------------------------
    attachments = []
    attachment_count = 0

    try:
        if project_request_id is not None:
            q = select(ProjectFile).where(ProjectFile.project_request_id == project_request_id)
            result = await db.execute(q)
            files = result.scalars().all()

            if files:
                attachments = [
                    {"stored_filename": f.stored_filename, "filename": f.filename}
                    for f in files
                ]
                attachment_count = len(attachments)

        logger.info("📎 Attachments resolved | count=%d", attachment_count)

    except Exception as e:
        # IMPORTANT: Do not crash the email send if attachments fail.
        logger.exception("❌ Attachment lookup failed (email will still send)")
        attachments = []
        attachment_count = 0

    # -------------------------------
    # SEND EMAIL (ALWAYS SEND)
    # -------------------------------
    subject = "Project Drawings and Photos"
    body = "Please see attached project drawings and photos."

    if attachment_count == 0:
        # Still send a proof-of-life email while attachments are being fixed
        body = (
            "Project email test: we received your email successfully.\n\n"
            "No attachments were found for this project_request_id yet."
        )

    try:
        send_project_email(
            to_email=email,
            subject=subject,
            body=body,
            attachments=attachments,
        )
        logger.info("✅ EMAIL SENT | to=%s | attachments=%d", email, attachment_count)

    except Exception as e:
        logger.exception("❌ EMAIL FAILED")
        # Return detail so curl shows the real reason immediately
        return JSONResponse(
            status_code=500,
            content={
                "error": "email_send_failed",
                "detail": str(e),
                "call_id": call_id,
                "project_request_id": project_request_id,
                "email": email,
                "attachments": attachment_count,
            },
        )

    return {
        "status": "success",
        "email": email,
        "call_id": call_id,
        "project_request_id": project_request_id,
        "attachments": attachment_count,
        "interest": interest,
    }