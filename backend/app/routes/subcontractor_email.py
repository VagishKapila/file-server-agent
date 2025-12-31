import logging
from typing import List, Union, Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.email_log import EmailLog
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("subcontractor-email")


class AttachmentIn(BaseModel):
    path: str
    filename: str


class SendSubEmailRequest(BaseModel):
    vendor_email: str
    project_request_id: Optional[int] = None
    subject: str
    message: str
    attachments: List[Union[int, AttachmentIn]]


async def _send_email_core(
    *,
    db: AsyncSession,
    vendor_email: str,
    project_request_id: Optional[int],
    subject: str,
    message: str,
    attachments: List[Union[int, AttachmentIn]],
    related_call_id: Optional[str] = None,
) -> Dict[str, Any]:

    resolved_attachments: List[Dict[str, str]] = []

    for a in attachments:
        if isinstance(a, int):
            res = await db.execute(
                select(ProjectFile).where(ProjectFile.id == a)
            )
            file = res.scalars().first()

            if not file:
                logger.warning("Attachment ID %s not found", a)
                continue

            # ✅ FIX: use real R2 key
            if not file.r2_path or not file.r2_path.startswith("r2://"):
                logger.warning("Attachment %s ignored (not R2)", a)
                continue

            resolved_attachments.append(
                {"path": file.r2_path, "filename": file.filename}
            )

        else:
            if not a.path.startswith("r2://"):
                logger.warning("Direct attachment ignored (not R2): %s", a.path)
                continue

            resolved_attachments.append(
                {"path": a.path, "filename": a.filename}
            )

    logger.info(
        "📧 Sending email → %s | attachments=%d",
        vendor_email,
        len(resolved_attachments),
    )

    send_project_email(
        to_email=vendor_email,
        subject=subject,
        body=message,
        attachments=resolved_attachments,
    )

    if project_request_id:
        try:
            db.add(
                EmailLog(
                    project_request_id=project_request_id,
                    recipient_email=vendor_email,
                    email_type="vendor_project_files",
                    related_call_id=related_call_id,
                )
            )
            await db.commit()
        except Exception:
            logger.exception("Email sent but logging failed")
            await db.rollback()

    return {
        "status": "ok",
        "sent_to": vendor_email,
        "attachments": len(resolved_attachments),
    }


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


async def send_vendor_email(payload: dict, db: AsyncSession):
    return await _send_email_core(
        db=db,
        vendor_email=payload["vendor_email"],
        project_request_id=payload.get("project_request_id"),
        subject=payload["subject"],
        message=payload["message"],
        attachments=payload.get("attachments", []),
        related_call_id=payload.get("related_call_id"),
    )