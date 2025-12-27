from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.unified_email_service import send_project_email

router = APIRouter(prefix="/retell", tags=["retell"])

logger = logging.getLogger("retell-webhook")
logger.setLevel(logging.INFO)


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    data = await request.json()
    logger.info("📞 WEBHOOK RECEIVED: %s", data)

    call = data.get("call", {})
    structured = call.get("call_analysis", {}).get("custom_analysis_data", {})

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    project_request_id = call.get("metadata", {}).get("project_request_id")
    call_id = call.get("call_id")

    if not email or not confirmed:
        return {"ok": True}

    if project_request_id is None:
        logger.error("❌ Missing project_request_id")
        return {"ok": True}

    q = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id
    )
    result = await db.execute(q)
    files = result.scalars().all()

    if not files:
        raise RuntimeError("DB HAS NO FILES — STOP")

    attachments = []
    for f in files:
        attachments.append({
            "filename": f.filename,
            "path": f.stored_path,
        })

    send_project_email(
        to_email=email,
        subject="Project Files",
        body=f"Files for project_request_id={project_request_id}",
        attachments=attachments,
    )

    return {
        "status": "success",
        "email": email,
        "project_request_id": project_request_id,
        "attachments": len(attachments),
    }