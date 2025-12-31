import logging
from typing import List, Union, Dict, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.email_log import EmailLog
from app.services.r2_client import get_r2_client

# 🚫 DO NOT import unified_email_service inside itself
# ✅ send_project_email is defined BELOW

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("unified-email")


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
# EMAIL SENDER (SINGLE SOURCE OF TRUTH)
# -------------------------------------------------------------------

def send_project_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    attachments: List[Dict[str, Any]],
):
    """
    attachments = [
        {
            "filename": "file.pdf",
            "content": b"...bytes..."
        }
    ]
    """
    from app.services.smtp_mailer import send_email  # local import = safe

    send_email(
        to_email=to_email,
        subject=subject,
        body=body,
        attachments=attachments,
    )


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

    resolved_attachments: List[Dict[str, Any]] = []
    r2 = get_r2_client()

    # ---------------- RESOLVE + DOWNLOAD ATTACHMENTS ----------------
    for a in attachments:
        if isinstance(a, int):
            res = await db.execute(
                select(ProjectFile).where(ProjectFile.id == a)
            )
            file = res.scalars().first()

            if not file or not file.stored_path:
                logger.warning("❌ Attachment ID %s not found", a)
                continue

            path = file.stored_path
            filename = file.filename
        else:
            path = a.path
            filename = a.filename

        if not path.startswith("r2://"):
            logger.warning("❌ Ignored attachment (not r2): %s", path)
            continue

        try:
            # r2://bucket/key
            r2_path = path.replace("r2://", "", 1)
            bucket, key = r2_path.split("/", 1)

            obj = r2.get_object(Bucket=bucket, Key=key)
            file_bytes = obj["Body"].read()

            resolved_attachments.append(
                {
                    "filename": filename,
                    "content": file_bytes,  # 🔑 REAL BYTES
                }
            )

        except Exception:
            logger.exception("❌ R2 download failed for %s", path)

    logger.info(
        "📧 Sending email → %s | attachments=%d",
        vendor_email,
        len(resolved_attachments),
    )

    # ---------------- SEND EMAIL ----------------
    send_project_email(
        to_email=vendor_email,
        subject=subject,
        body=message,
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
            logger.exception("❌ Email sent but logging failed")
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