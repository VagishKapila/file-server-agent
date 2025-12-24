from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db import get_db
from backend.app.models.activity_log import ActivityLog
from backend.app.models.email_log import EmailLog
from backend.app.models.project_files import ProjectFile
from backend.app.models.vendor_call_state import VendorCallState

router = APIRouter(prefix="/project-report", tags=["project-report"])


@router.get("/{project_request_id}")
async def get_project_report(
    project_request_id: int,
    db: AsyncSession = Depends(get_db),
):
    # ---- Calls / outcomes ----
    calls = await db.execute(
        select(
            VendorCallState.vendor_phone,
            VendorCallState.trade,
            VendorCallState.attempts,
            VendorCallState.status,
            VendorCallState.last_attempt_at,
        ).where(VendorCallState.project_request_id == project_request_id)
    )

    # ---- Emails ----
    emails = await db.execute(
        select(
            EmailLog.recipient_email,
            EmailLog.email_type,
            EmailLog.sent_at,
        ).where(EmailLog.project_request_id == project_request_id)
    )

    # ---- Files ----
    files = await db.execute(
        select(
            ProjectFile.filename,
            ProjectFile.file_size,
            ProjectFile.file_type,
            ProjectFile.uploaded_at,
        ).where(ProjectFile.project_request_id == project_request_id)
    )

    return {
        "calls": [
            {
                "vendor_phone": c.vendor_phone,
                "trade": c.trade,
                "attempts": c.attempts,
                "status": c.status,
                "last_attempt_at": c.last_attempt_at,
            }
            for c in calls
        ],
        "emails": [
            {
                "recipient": e.recipient_email,
                "type": e.email_type,
                "sent_at": e.sent_at,
            }
            for e in emails
        ],
        "files": [
            {
                "filename": f.filename,
                "size": f.file_size,
                "type": f.file_type,
                "uploaded_at": f.uploaded_at,
            }
            for f in files
        ],
    }
