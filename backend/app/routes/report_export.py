from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import os

from app.db import get_db
from app.routes.reports import project_report
from app.services.report_pdf import generate_project_report_pdf
from app.models.project_files import ProjectFile

router = APIRouter(prefix="/report-export", tags=["Report Export"])

# Canonical upload root
UPLOAD_ROOT = os.getenv("UPLOAD_DIR", "/app/bains_uploads")


@router.get("/project/{project_request_id}")
def export_project_report_pdf(
    project_request_id: int,
    db: Session = Depends(get_db),
):
    """
    Generates a persistent PDF report AND registers it as a ProjectFile
    so it can be attached via email / Retell.
    """

    # --------------------------------------------------
    # FETCH PROJECT DATA (fails fast if not found)
    # --------------------------------------------------
    report_data = project_report(project_request_id, db)
    if not report_data:
        raise HTTPException(status_code=404, detail="Project not found")

    filename = f"project_report_{project_request_id}.pdf"

    # --------------------------------------------------
    # PERSISTENT PATH
    # /app/bains_uploads/reports/<project_request_id>/
    # --------------------------------------------------
    output_dir = os.path.join(
        UPLOAD_ROOT,
        "reports",
        str(project_request_id),
    )
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.join(output_dir, filename)

    # --------------------------------------------------
    # GENERATE PDF
    # --------------------------------------------------
    generate_project_report_pdf(report_data, output_path)

    if not os.path.exists(output_path):
        raise HTTPException(status_code=500, detail="PDF generation failed")

    # --------------------------------------------------
    # REGISTER AS PROJECT FILE (CRITICAL STEP)
    # --------------------------------------------------
    existing = (
        db.query(ProjectFile)
        .filter(
            ProjectFile.project_request_id == project_request_id,
            ProjectFile.stored_path == output_path,
        )
        .first()
    )

    if not existing:
        record = ProjectFile(
            project_request_id=project_request_id,
            filename=filename,
            stored_path=output_path,          # ABSOLUTE PATH
            file_type="application/pdf",
            file_size=os.path.getsize(output_path),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

    return {
        "status": "ok",
        "file_path": output_path,
        "filename": filename,
    }