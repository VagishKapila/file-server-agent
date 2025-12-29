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

    # ✅ FINAL, DEFENSIVE PARSING LOGIC (KEEP)
    structured = (
        data.get("custom_analysis")
        or call.get("custom_analysis")
        or call.get("call_analysis", {}).get("custom_analysis_data")
        or {}
    )

    email = structured.get("email")
    confirmed = structured.get("email_confirmed") is True
    raw_id = call.get("metadata", {}).get("project_request_id")

    try:
        project_request_id = int(raw_id)
    except (TypeError, ValueError):
        logger.warning("RETELL | invalid project_request_id: %s", raw_id)
        return {"ok": True}

    # ✅ KEEP THIS LOG (safe + valuable)
    logger.info(
        "RETELL PARSED | email=%s confirmed=%s project_request_id=%s",
        email, confirmed, project_request_id
    )

    if not email or not confirmed:
        return {"ok": True}

    # 🔍 DB QUERY (NOW TYPE-SAFE)
    stmt = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id
    )
    res = await db.execute(stmt)
    files = res.scalars().all()

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