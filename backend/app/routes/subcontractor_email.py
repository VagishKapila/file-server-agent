from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Union
import logging
from pydantic import BaseModel

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("subcontractor-email")


# --------------------------------------------------
# REQUEST SCHEMA (JSON BODY)
# --------------------------------------------------
class AttachmentIn(BaseModel):
    path: str
    filename: str


class SendSubEmailRequest(BaseModel):
    vendor_email: str
    project_request_id: int
    subject: str
    message: str
    attachments: List[Union[int, AttachmentIn]]


@router.post("/send")
async def send_subcontractor_email(
    payload: SendSubEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    resolved_attachments = []

    for a in payload.attachments:
        # ----------------------------------
        # CASE 1: DB attachment by ID
        # ----------------------------------
        if isinstance(a, int):
            stmt = select(ProjectFile).where(ProjectFile.id == a)
            res = await db.execute(stmt)
            file = res.scalars().first()

            if not file:
                raise HTTPException(
                    status_code=404,
                    detail=f"Attachment ID {a} not found",
                )

            resolved_attachments.append(
                {
                    "path": file.stored_path,
                    "filename": file.filename,
                }
            )

        # ----------------------------------
        # CASE 2: Direct path attachment
        # ----------------------------------
        else:
            resolved_attachments.append(
                {
                    "path": a.path,
                    "filename": a.filename,
                }
            )

    send_project_email(
        to_email=payload.vendor_email,
        subject=payload.subject,
        body=payload.message,
        attachments=resolved_attachments,
    )

    logger.info(
        "Email sent to %s with %d attachments",
        payload.vendor_email,
        len(resolved_attachments),
    )

    return {
        "status": "ok",
        "sent_to": payload.vendor_email,
        "attachments": len(resolved_attachments),
    }