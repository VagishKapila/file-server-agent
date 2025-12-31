import logging
from typing import List, Union, Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.email_log import EmailLog

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("subcontractor-email")


# -------------------------------------------------------------------
# HELPERS
# -------------------------------------------------------------------

def _safe_text(s: str) -> str:
    if not s:
        return ""
    return (
        s.encode("utf-8", "ignore")
        .decode("utf-8", "ignore")
        .replace("\x00", "")
    )


# -------------------------------------------------------------------
# SCHEMAS
# -------------------------------------------------------------------

class AttachmentIn(BaseModel):
    path: str
    filename: str


class SendSubEmailRequest(BaseModel):
    vendor_email: str
    project_request_id: Optional[int] = None
    subject: str
    message: str
    attachments: List[Union[int, AttachmentIn]]


# -------------------------------------------------------------------
# CORE EMAIL LOGIC
# -------------------------------------------------------------------

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

    # ---------------- RESOLVE ATTACHMENTS ----------------
    for a in attachments:
        if isinstance(a, int):
            res = await db.execute(
                select(ProjectFile).where(ProjectFile.id == a)
            )
            file = res.scalars().first()

            if not file:
                logger.warning("❌ Attachment ID %s not found", a)
                continue

            if not file.stored_path or not file.stored_path.startswith("r2://"):
                logger.warning(
                    "❌ Attachment %s ignored (invalid stored_path: %s)",
                    a,
                    file.stored_path,
                )
                continue

            resolved_attachments.append(
                {"path": file.stored_path, "filename": file.filename}
            )

        else:
            if not a.path.startswith("r2://"):
                logger.warning(
                    "❌ Direct attachment ignored (not R2): %s", a.path
                )
                continue

            resolved_attachments.append(
                {"path": a.path, "filename": a.filename}
            )

    if attachments and not resolved_attachments:
        logger.error(
            "⚠️ Attachments requested but NONE resolved | requested=%s",
            attachments,
        )

    logger.info(
        "📧 Sending email → %s | resolved_attachments=%d",
        vendor_email,
        len(resolved_attachments),
    )

    # ---------------- SEND EMAIL ----------------
    send_project_email(
        to_email=vendor_email,
        subject=_safe_text(subject),
        body=_safe_text(message),
        attachments=resolved_attachments,
    )

    # ---------------- EMAIL LOG ----------------
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
            logger.exception("❌ Email sent but log failed")
            await db.rollback()

    return {
        "status": "ok",
        "sent_to": vendor_email,
        "requested_attachments": len(attachments),
        "resolved_attachments": len(resolved_attachments),
    }


# -------------------------------------------------------------------
# PUBLIC API
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
# INTERNAL — RETELL WEBHOOK
# -------------------------------------------------------------------

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