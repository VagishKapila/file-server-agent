import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.report_pdf import generate_project_report_pdf

router = APIRouter(prefix="/report-export", tags=["Report Export"])
logger = logging.getLogger("report-export")


@router.get("/project/{project_request_id}")
async def export_project_report_pdf(
    project_request_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a PDF in memory, uploads to R2,
    and registers the R2 object in project_files.
    """

    # --------------------------------------------------
    # Minimal SAFE report_data (no route calls)
    # --------------------------------------------------
    report_data = {
        "project_request_id": project_request_id,
        "subcontractors": [],
        "materials": [],
    }

    logger.info("Starting PDF generation for project_request_id=%s", project_request_id)

    # --------------------------------------------------
    # GENERATE + UPLOAD PDF (IN MEMORY)
    # --------------------------------------------------
    try:
        pdf_result = generate_project_report_pdf(report_data)
    except Exception as e:
        logger.exception("PDF generation failed")
        raise HTTPException(status_code=500, detail=str(e))

    r2_uri = pdf_result["r2_uri"]
    r2_key = pdf_result["r2_key"]
    filename = pdf_result["filename"]
    file_size = pdf_result["file_size"]

    logger.info(
        "PDF uploaded to R2 key=%s size=%s bytes",
        r2_key,
        file_size,
    )

    # --------------------------------------------------
    # REGISTER IN project_files (R2 PATH)
    # --------------------------------------------------
    stmt = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id,
        ProjectFile.stored_path == r2_uri,
    )
    res = await db.execute(stmt)
    existing = res.scalars().first()

    if not existing:
        record = ProjectFile(
            project_request_id=project_request_id,
            filename=filename,
            stored_path=r2_uri,          # ✅ r2://bucket/key
            file_type="application/pdf",
            file_size=file_size,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        logger.info("Registered PDF in project_files id=%s", record.id)
    else:
        logger.info("PDF already registered id=%s", existing.id)

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "r2_uri": r2_uri,
        "filename": filename,
        "file_size": file_size,
    }