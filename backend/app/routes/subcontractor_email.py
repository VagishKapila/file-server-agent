from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Union
import logging

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/email/sub", tags=["subcontractor-email"])
logger = logging.getLogger("subcontractor-email")


@router.post("/send")
async def send_subcontractor_email(
    vendor_email: str,
    project_request_id: int,
    subject: str,
    message: str,
    attachments: List[Union[int, dict]],
    db: AsyncSession = Depends(get_db),
):
    """
    attachments supports:
    - integer ProjectFile IDs
    - OR { path: "r2://...", filename: "..." }
    """

    resolved_attachments = []

    for a in attachments:
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
        # CASE 2: Direct R2 / path attachment
        # ----------------------------------
        elif isinstance(a, dict):
            if "path" not in a or "filename" not in a:
                raise HTTPException(
                    status_code=400,
                    detail="Attachment objects must include path and filename",
                )

            resolved_attachments.append(
                {
                    "path": a["path"],
                    "filename": a["filename"],
                }
            )

        else:
            raise HTTPException(
                status_code=400,
                detail="Invalid attachment format",
            )

    send_project_email(
        to_email=vendor_email,
        subject=subject,
        body=message,
        attachments=resolved_attachments,
    )

    logger.info(
        "Email sent to %s with %s attachments",
        vendor_email,
        len(resolved_attachments),
    )

    return {
        "status": "ok",
        "sent_to": vendor_email,
        "attachments": len(resolved_attachments),
    }