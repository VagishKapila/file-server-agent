from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email
from app.services.r2_client import get_r2_client

router = APIRouter(prefix="/browser", tags=["browser-email"])


class BrowserEmailRequest(BaseModel):
    project_request_id: int
    to_email: str


@router.post("/send-email")
async def send_browser_email(
    payload: BrowserEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    r2 = get_r2_client()
    attachments = []

    files = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == payload.project_request_id)
    )

    for f in files.scalars():
        if not f.stored_path or not f.stored_path.startswith("r2://"):
            continue

        _, key = f.stored_path.replace("r2://", "", 1).split("/", 1)

        try:
            obj = r2.get_object(Bucket=r2.bucket, Key=key)
            attachments.append({
                "filename": f.filename,
                "content": obj["Body"].read(),
            })
        except Exception:
            continue

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