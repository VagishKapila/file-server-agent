from fastapi import APIRouter, Request, Depends
import logging
import os
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.activity_log import ActivityLog
from app.models.email_log import EmailLog
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

BASE_DIR = os.getenv("APP_BASE_DIR", os.getcwd())

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()

    # 🔴 TEMP DEBUG — DO NOT REMOVE UNTIL VERIFIED
    logger.error("🔥 RETELL RAW PAYLOAD = %s", data)

    structured = (
        data.get("structured_output")
        or data.get("extracted_data")
        or data.get("conversation", {}).get("structured_output")
        or {}
    )

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    interest = structured.get("interest")

    if not email or not email_confirmed:
        logger.error("🟡 RETELL: No confirmed email | payload=%s", structured)
        return {"ok": True}

    # 🔴 TEMP DEBUG — CONFIRM PARSE
    logger.error(
        "✅ RETELL EMAIL CONFIRMED | email=%s | interest=%s",
        email,
        interest,
    )

    project_request_id = data.get("metadata", {}).get("project_request_id")

    attachments = []
    if project_request_id:
        files = await db.execute(
            select(ProjectFile)
            .where(ProjectFile.project_request_id == project_request_id)
        )

        for f in files.scalars():
            if not f.stored_path:
                continue

            path = (
                f.stored_path
                if os.path.isabs(f.stored_path)
                else os.path.join(BASE_DIR, f.stored_path)
            )

            if os.path.exists(path):
                attachments.append({
                    "path": path,
                    "type": f.file_type,
                    "name": f.filename,
                })

    # ✅ SEND EMAIL (reuse working pipeline)
    send_project_email(
        to_email=email,
        subject="Project Drawings & Photos",
        body="Please see the attached drawings and photos.",
        attachments=attachments,
    )

    # ✅ LOG SUCCESS
    db.add(
        EmailLog(
            project_request_id=project_request_id,
            recipient_email=email,
            email_type="subcontractor",
            related_call_id=data.get("call_id"),
        )
    )
    await db.commit()

    return {"ok": True}
