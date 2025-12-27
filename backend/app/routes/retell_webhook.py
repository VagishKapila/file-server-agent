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


@router.post("/webhook")
async def retell_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    call = data.get("call", {})
    structured = call.get("call_analysis", {}).get("custom_analysis_data", {})

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    project_request_id = call.get("metadata", {}).get("project_request_id")

    if not email or not confirmed or project_request_id is None:
        return {"ok": True}

    q = select(ProjectFile).where(ProjectFile.project_request_id == project_request_id)
    result = await db.execute(q)
    files = result.scalars().all()

    attachments = [
        {"filename": f.filename, "path": f.stored_path}
        for f in files
        if f.stored_path
    ]

    send_project_email(
        to_email=email,
        subject="Project Drawings and Photos",
        body=f"Files for project_request_id={project_request_id}",
        attachments=attachments,
    )

    return {
        "status": "success",
        "email": email,
        "project_request_id": project_request_id,
        "attachments": len(attachments),
    }
