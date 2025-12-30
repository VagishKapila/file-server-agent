import logging
from typing import List, Union, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.email_log import EmailLog
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("subcontractor-email")


# -------------------------------------------------------------------
# SCHEMAS
# -------------------------------------------------------------------

class AttachmentIn(BaseModel):
    path: str
    filename: str


class SendSubEmailRequest(BaseModel):
    vendor_email: str
    project_request_id: int
    subject: str
    message: str
    attachments: List[Union[int, AttachmentIn]]


# -------------------------------------------------------------------
# SHARED CORE LOGIC (USED BY API + WEBHOOK)
# -------------------------------------------------------------------

async def _send_email_core(
    *,
    db: AsyncSession,
    vendor_email: str,
    project_request_id: int,
    subject: str,
    message: str,
    attachments: List[Union[int, AttachmentIn]],
    related_call_id: str | None = None,
) -> Dict[str, Any]:

    resolved_attachments: List[Dict[str, str]] = []

    for a in attachments:
        # ---------------- DB FILE BY ID ----------------
        if isinstance(a, int):
            stmt = select(ProjectFile).where(ProjectFile.id == a)
            res = await db.execute(stmt)
            file = res.scalars().first()

            if not file:
                logger.warning("Attachment ID %s not found in DB", a)
                continue

            if not file.stored_path or not file.stored_path.startswith("r2://"):
                logger.warning("Attachment %s ignored (not R2)", a)
                continue

            resolved_attachments.append(
                {
                    "path": file.stored_path,
                    "filename": file.filename,
                }
            )

        # ---------------- DIRECT PATH ----------------
        else:
            if not a.path.startswith("r2://"):
                logger.warning("Direct attachment ignored (not R2): %s", a.path)
                continue

            resolved_attachments.append(
                {
                    "path": a.path,
                    "filename": a.filename,
                }
            )

    logger.info(
        "Sending email → %s | project=%s | attachments=%d",
        vendor_email,
        project_request_id,
        len(resolved_attachments),
    )

    # ---- SEND EMAIL (do not block on attachments) ----
    send_project_email(
        to_email=vendor_email,
        subject=subject,
        body=message,
        attachments=resolved_attachments,
    )

    # ---- ALWAYS LOG EMAIL ATTEMPT ----
    email_log = EmailLog(
        project_request_id=project_request_id,
        recipient_email=vendor_email,
        email_type="vendor_project_files",
        related_call_id=related_call_id,
    )

    db.add(email_log)
    await db.commit()

    logger.info(
        "Email logged → %s | project=%s",
        vendor_email,
        project_request_id,
    )

    return {
        "status": "ok",
        "sent_to": vendor_email,
        "attachments": len(resolved_attachments),
    }


# -------------------------------------------------------------------
# PUBLIC API ENDPOINT
# -------------------------------------------------------------------

@router.post("/send")
async def send_subcontractor_email(
    payload: SendSubEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    return await _send_email_core(
        db=db,
        vendor_email=payload.vendor_email,
        project_request_id=payload.project_request_id,
        subject=payload.subject,
        message=payload.message,
        attachments=payload.attachments,
    )


# -------------------------------------------------------------------
# INTERNAL USE — CALLED BY RETELL WEBHOOK
# -------------------------------------------------------------------

async def send_vendor_email(payload: dict, db: AsyncSession):
    """
    Expected payload keys:
      - vendor_email
      - project_request_id
      - subject
      - message
      - attachments
      - related_call_id (optional)
    """

    required = {"vendor_email", "subject", "message", "attachments"}
    missing = required - payload.keys()

    if missing:
        raise ValueError(f"Missing required email fields: {missing}")

    return await _send_email_core(
        db=db,
        vendor_email=payload["vendor_email"],
        project_request_id=payload.get("project_request_id", 0),
        subject=payload["subject"],
        message=payload["message"],
        attachments=payload.get("attachments", []),
        related_call_id=payload.get("related_call_id"),
    )