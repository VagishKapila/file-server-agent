from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.models.project_files import ProjectFile

router = APIRouter(prefix="/_debug", tags=["_debug"])


@router.get("/project-files")
def debug_project_files(
    project_request_id: int = Query(..., description="Project Request ID"),
    db: Session = Depends(get_db),
):
    """
    READ-ONLY DEBUG ENDPOINT
    Returns exactly what exists in project_files for a project.
    No side effects. Safe in prod.
    """

    rows = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_request_id == project_request_id)
        .order_by(ProjectFile.uploaded_at.desc())
        .all()
    )

    return {
        "project_request_id": project_request_id,
        "count": len(rows),
        "files": [
            {
                "id": r.id,
                "filename": r.filename,
                "stored_path": r.stored_path,
                "file_type": r.file_type,
                "file_size": r.file_size,
                "shared": r.shared,
                "uploaded_at": r.uploaded_at.isoformat() if r.uploaded_at else None,
            }
            for r in rows
        ],
    }
