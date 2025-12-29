import logging
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])
logger = logging.getLogger("retell-webhook")


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()

    call = data.get("call", {})
    structured = call.get("call_analysis", {}).get("custom_analysis_data", {})

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    project_request_id = call.get("metadata", {}).get("project_request_id")

    logger.info(
        "RETELL PARSED | email=%s confirmed=%s project_request_id=%s raw=%s",
        email,
        confirmed,
        project_request_id,
        structured
    )

    if not email or not confirmed or not project_request_id:
        return {"ok": True}

    stmt = select(ProjectFile).where(ProjectFile.project_request_id == project_request_id)
    res = await db.execute(stmt)
    files = res.scalars().all()

    # ✅ ONLY R2 FILES
    attachments = [
        {"filename": f.filename, "path": f.stored_path}
        for f in files
        if f.stored_path and f.stored_path.startswith("r2://")
    ]

    send_project_email(
        to_email=email,
        subject="Project Files",
        body=f"Attached files for project_request_id={project_request_id}",
        attachments=attachments,
    )

    return {
        "status": "sent",
        "email": email,
        "attachments": len(attachments),
    }
