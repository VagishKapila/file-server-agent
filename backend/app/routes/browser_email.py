from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from backend.app.db import get_db
from backend.app.models.project_files import ProjectFile
from backend.app.services.unified_email_service import send_project_email

BASE_DIR = os.getenv("APP_BASE_DIR", os.getcwd())

router = APIRouter(prefix="/browser", tags=["browser-email"])


class BrowserEmailRequest(BaseModel):
    project_request_id: int
    to_email: str


@router.post("/send-email")
async def send_browser_email(
    payload: BrowserEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    files = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == payload.project_request_id)
    )

    attachments = []
    for f in files.scalars():
        if not f.stored_path or not f.file_type:
            continue

        path = (
            f.stored_path
            if os.path.isabs(f.stored_path)
            else os.path.join(BASE_DIR, f.stored_path)
        )

        if not os.path.exists(path):
            continue

        attachments.append({
            "path": path,
            "type": f.file_type,
            "name": f.filename,
        })

    # ✅ SINGLE SOURCE OF TRUTH
    send_project_email(
        to_email=payload.to_email,
        subject="Project Drawings & Photos",
        body="Please find drawings and photos attached.",
        attachments=attachments,
    )

    return {
        "ok": True,
        "attachments_sent": len(attachments),
    }