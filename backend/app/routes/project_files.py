import os, uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from pathlib import Path

from app.db import get_db
from app.models.project_files import ProjectFile

router = APIRouter(prefix="/project-files", tags=["project-files"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
if not UPLOAD_DIR:
    raise RuntimeError("UPLOAD_DIR must be set")

UPLOAD_PATH = Path(UPLOAD_DIR)
UPLOAD_PATH.mkdir(parents=True, exist_ok=True)


@router.post("/upload")
async def upload_project_files(
    project_request_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    saved = []

    for file in files:
        data = await file.read()

        ext = Path(file.filename).suffix
        stored_name = f"{uuid.uuid4().hex}{ext}"
        stored_path = UPLOAD_PATH / stored_name

        with open(stored_path, "wb") as f:
            f.write(data)

        record = ProjectFile(
            project_request_id=project_request_id,
            filename=file.filename,
            stored_path=str(stored_path),
            file_type=file.content_type,
            file_size=len(data),
        )

        db.add(record)
        await db.commit()
        await db.refresh(record)

        saved.append({
            "id": record.id,
            "filename": record.filename,
        })

    return {"status": "ok", "files": saved}