import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile

router = APIRouter(prefix="/project-files", tags=["project-files"])

# ------------------------------------------------------------------
# Canonical upload root (already set on server, per your note)
# Example: /app/bains_uploads
# ------------------------------------------------------------------
UPLOAD_DIR = os.getenv("UPLOAD_DIR")
if not UPLOAD_DIR:
    raise RuntimeError("UPLOAD_DIR must be set")

UPLOAD_ROOT = Path(UPLOAD_DIR)
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_project_files(
    project_request_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    saved = []

    # ------------------------------------------------------------------
    # Project-scoped directory (critical for scale + clarity)
    # /app/bains_uploads/projects/<project_request_id>/
    # ------------------------------------------------------------------
    project_dir = UPLOAD_ROOT / "projects" / str(project_request_id)
    project_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        data = await file.read()

        ext = Path(file.filename).suffix
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = project_dir / stored_name

        with open(stored_path, "wb") as f:
            f.write(data)

        record = ProjectFile(
            project_request_id=project_request_id,
            filename=file.filename,
            stored_path=str(stored_path),  # ABSOLUTE PATH
            file_type=file.content_type,
            file_size=len(data),
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        saved.append(
            {
                "id": record.id,
                "filename": record.filename,
            }
        )

    return {
        "status": "ok",
        "files": saved,
    }