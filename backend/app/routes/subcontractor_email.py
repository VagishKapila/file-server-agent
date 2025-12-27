from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
import os

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.email_service import send_email_with_attachments

router = APIRouter(prefix="/email/sub", tags=["email"])
logger = logging.getLogger("vendor-email")


@router.post("/send")
async def send_vendor_email(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    logger.info("📞 /email/sub/send called")

    vendor_email = payload.get("vendor_email")
    attachment_ids = payload.get("attachments", [])
    project_request_id = payload.get("project_request_id")
    subject = payload.get("subject", "Project Files")
    message = payload.get("message", "Please see attached files.")

    if not vendor_email:
        raise HTTPException(status_code=400, detail="vendor_email required")

    # --------------------------------------------------
    # RESOLVE ATTACHMENTS
    # --------------------------------------------------
    files = []

    # OPTION A: explicit attachment IDs
    if attachment_ids:
        if not all(isinstance(i, int) for i in attachment_ids):
            raise HTTPException(
                status_code=400,
                detail="attachments must be integer IDs",
            )

        logger.info("📎 Resolving attachments by IDs: %s", attachment_ids)

        q = select(ProjectFile).where(ProjectFile.id.in_(attachment_ids))
        result = await db.execute(q)
        files = result.scalars().all()

    # OPTION B: auto-attach by project_request_id
    elif project_request_id:
        logger.info(
            "📎 Resolving attachments by project_request_id=%s",
            project_request_id,
        )

        q = select(ProjectFile).where(
            ProjectFile.project_request_id == project_request_id
        )
        result = await db.execute(q)
        files = result.scalars().all()

    if not files:
        logger.warning("❌ No files found to attach")
        raise HTTPException(status_code=404, detail="No files found to attach")

    # Build attachment payload
    attachments = [
        {
            "path": f.stored_path,
            "filename": f.filename,
        }
        for f in files
    ]

    logger.info(
        "📧 Sending email to=%s attachments=%d",
        vendor_email,
        len(attachments),
    )

    # --------------------------------------------------
    # ATTACHMENT DIAGNOSTICS (READ-ONLY)
    # --------------------------------------------------
    for a in attachments:
        logger.info(
            "📂 Attachment resolved filename=%s path=%s exists=%s",
            a["filename"],
            a["path"],
            os.path.exists(a["path"]) if a.get("path") else None,
        )

    # --------------------------------------------------
    # SEND EMAIL
    # --------------------------------------------------
    logger.info("✉️ Calling send_email_with_attachments")

    send_email_with_attachments(
        to_email=vendor_email,
        subject=subject,
        body=message,
        attachments=attachments,
    )

    logger.info("✅ Email send invoked successfully")

    return {
        "status": "sent",
        "vendor_email": vendor_email,
        "attachments": [a["filename"] for a in attachments],
    }