from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

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
    # --------------------------------------------------
    # 1. READ PAYLOAD SAFELY
    # --------------------------------------------------
    try:
        data = await request.json()
    except Exception:
        logger.exception("❌ Invalid JSON received")
        return JSONResponse(status_code=400, content={"error": "invalid_json"})

    logger.info("📞 RETELL WEBHOOK RECEIVED")
    logger.info(data)

    # --------------------------------------------------
    # 2. EXTRACT CALL + STRUCTURED DATA (RETELL STANDARD)
    # --------------------------------------------------
    call = data.get("call", {})

    structured = (
        call.get("call_analysis", {})
            .get("custom_analysis_data", {})
        or {}
    )

    email = structured.get("email")
    email_confirmed = structured.get("email_confirmed") is True
    project_request_id = call.get("metadata", {}).get("project_request_id")
    call_id = call.get("call_id")

    logger.info(
        "📌 call_id=%s | project_request_id=%s | email=%s | confirmed=%s",
        call_id,
        project_request_id,
        email,
        email_confirmed,
    )

    # --------------------------------------------------
    # 3. HARD GUARDS (NO CRASHES)
    # --------------------------------------------------
    if not email or not email_confirmed:
        logger.info("🟡 Email missing or not confirmed — skipping")
        return {"ok": True}

    if project_request_id is None:
        logger.error("❌ project_request_id missing — cannot attach files")
        return {"ok": True}

    # --------------------------------------------------
    # 4. LOAD PROJECT FILES FROM DB
    # --------------------------------------------------
    q = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id
    )
    result = await db.execute(q)
    files = result.scalars().all()

    if not files:
        logger.warning(
            "⚠️ No files found for project_request_id=%s",
            project_request_id,
        )
        return {
            "status": "no_files",
            "email": email,
            "project_request_id": project_request_id,
        }

    # --------------------------------------------------
    # 5. RESOLVE LOCAL FILE PATHS (CRITICAL)
    # --------------------------------------------------
    attachments = []

    for f in files:
        path = f.stored_path

        if not path:
            logger.error("❌ stored_path missing in DB row id=%s", f.id)
            continue

        if not os.path.exists(path):
            logger.error("❌ File missing on disk: %s", path)
            continue

        attachments.append({
            "filename": f.filename,
            "path": path,   # ✅ LOCAL FILE SYSTEM PATH
        })

    logger.info(
        "📎 Attachments resolved from disk: %d",
        len(attachments),
    )

    if not attachments:
        logger.warning(
            "⚠️ Files exist in DB but none found on disk — aborting email send"
        )
        return {
            "status": "files_missing_on_disk",
            "email": email,
            "project_request_id": project_request_id,
        }

    # --------------------------------------------------
    # 6. SEND EMAIL (ONLY PLACE ALLOWED TO FAIL HARD)
    # --------------------------------------------------
    try:
        send_project_email(
            to_email=email,
            subject="Project Drawings and Photos",
            body=f"Attached are the project files for project_request_id={project_request_id}.",
            attachments=attachments,
        )
    except Exception:
        logger.exception("❌ EMAIL SEND FAILED")
        return JSONResponse(
            status_code=500,
            content={"error": "email_send_failed"},
        )

    logger.info(
        "📩 Email sent successfully → %s | attachments=%d",
        email,
        len(attachments),
    )

    return {
        "status": "success",
        "email": email,
        "project_request_id": project_request_id,
        "attachments": len(attachments),
    }