# backend/app/routes/report_export.py

import os
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.report_pdf import generate_project_report_pdf

# IMPORTANT:
# This must be the BACKEND service route (backendaivagi-production),
# not the relay (file-server-agent-production).

router = APIRouter(prefix="/report-export", tags=["Report Export"])
logger = logging.getLogger("report-export")

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
if not UPLOAD_DIR:
    raise RuntimeError("UPLOAD_DIR must be set")

UPLOAD_ROOT = Path(UPLOAD_DIR)


@router.get("/project/{project_request_id}")
async def export_project_report_pdf(
    project_request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a persistent PDF report AND registers it as a ProjectFile
    so it can be attached via email / Retell.
    """

    # --------------------------------------------------
    # Build minimal report_data (do NOT call route handlers directly)
    # If you already have a service/helper that returns report_data,
    # swap it in here. For now, keep it minimal and safe.
    # --------------------------------------------------
    # If you have an existing helper like `project_report(project_request_id, db)`
    # AND it's async-safe, you can use it. Otherwise this minimal report
    # prevents crashes and still generates a PDF.

    report_data = {
        "project_request_id": project_request_id,
        "subcontractors": [],
        "materials": [],
    }

    filename = f"project_report_{project_request_id}.pdf"

    # Persistent path:
    # /app/bains_uploads/reports/<project_request_id>/project_report_<id>.pdf
    output_dir = UPLOAD_ROOT / "reports" / str(project_request_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / filename

    logger.info("Generating PDF report at: %s", str(output_path))

    try:
        generate_project_report_pdf(report_data, str(output_path))
    except Exception as e:
        logger.exception("PDF generation crashed: %s", e)
        raise HTTPException(status_code=500, detail="PDF generation crashed")

    if not output_path.exists():
        logger.error("PDF generation failed (file not found): %s", str(output_path))
        raise HTTPException(status_code=500, detail="PDF generation failed")

    file_size = output_path.stat().st_size
    logger.info("PDF generated OK size=%s path=%s", file_size, str(output_path))

    # --------------------------------------------------
    # Register in project_files so Retell/email can attach it
    # --------------------------------------------------
    stmt = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id,
        ProjectFile.stored_path == str(output_path),
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()

    if not existing:
        record = ProjectFile(
            project_request_id=project_request_id,
            filename=filename,
            stored_path=str(output_path),      # ABSOLUTE PATH
            file_type="application/pdf",
            file_size=file_size,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info("Registered PDF in project_files id=%s", record.id)
    else:
        logger.info("PDF already registered in project_files id=%s", existing.id)

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "file_path": str(output_path),
        "filename": filename,
        "file_size": file_size,
    }