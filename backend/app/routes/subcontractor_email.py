import logging
from typing import List, Union, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.models.email_log import EmailLog
from app.services.unified_email_service import send_project_email
from app.services.r2_client import get_r2_client

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


@router.post("/send")
async def send_subcontractor_email(
    payload: SendSubEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    r2 = get_r2_client()
    resolved_attachments = []

    for a in payload.attachments:
        if isinstance(a, int):
            res = await db.execute(
                select(ProjectFile).where(ProjectFile.id == a)
            )
            file = res.scalars().first()

            if not file or not file.stored_path:
                logger.warning("Missing attachment id=%s", a)
                continue

            path = file.stored_path
            filename = file.filename
        else:
            path = a.path
            filename = a.filename

        if not path.startswith("r2://"):
            logger.warning("Ignoring non-R2 attachment: %s", path)
            continue

        _, key = path.replace("r2://", "", 1).split("/", 1)

        try:
            obj = r2.get_object(Bucket=r2.bucket, Key=key)
            file_bytes = obj["Body"].read()

            resolved_attachments.append({
                "filename": filename,
                "content": file_bytes,
            })

        except Exception:
            logger.exception("R2 download failed: %s", path)

    send_project_email(
        to_email=payload.vendor_email,
        subject=payload.subject,
        body=payload.message,
        attachments=resolved_attachments,
    )

    if payload.project_request_id:
        db.add(
            EmailLog(
                project_request_id=payload.project_request_id,
                recipient_email=payload.vendor_email,
                email_type="vendor_project_files",
            )
        )
        await db.commit()

    return {
        "status": "ok",
        "sent_to": payload.vendor_email,
        "attachments": len(resolved_attachments),
    }


# ---- INTERNAL (RETELL) ----
async def send_vendor_email(payload: dict, db: AsyncSession):
    req = SendSubEmailRequest(
        vendor_email=payload["vendor_email"],
        project_request_id=payload.get("project_request_id"),
        subject=payload["subject"],
        message=payload["message"],
        attachments=payload.get("attachments", []),
    )
    return await send_subcontractor_email(req, db)