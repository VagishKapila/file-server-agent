from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db import get_db
from app.models.project_files import ProjectFile

router = APIRouter(prefix="/_debug", tags=["debug"])

@router.get("/project-files")
def list_project_files(project_request_id: int, db: Session = Depends(get_db)):
    files = (
        db.query(ProjectFile)
        .filter(ProjectFile.project_request_id == project_request_id)
        .all()
    )

    return {
        "count": len(files),
        "files": [
            {
                "id": f.id,
                "filename": f.filename,
                "stored_path": f.stored_path,
                "file_type": f.file_type,
                "file_size": f.file_size,
            }
            for f in files
        ],
    }