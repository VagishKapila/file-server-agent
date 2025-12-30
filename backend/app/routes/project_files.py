import uuid
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project_files import ProjectFile
from app.services.r2_uploader import upload_file_to_r2

router = APIRouter(prefix="/project-files", tags=["project-files"])


@router.post("/upload")
async def upload_project_files(
    project_request_id: int = Form(...),
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    records = []
    response_files = []

    for file in files:
        data = await file.read()
        if not data:
            continue

        ext = ""
        if "." in file.filename:
            ext = "." + file.filename.rsplit(".", 1)[-1]

        stored_name = f"{uuid.uuid4().hex}{ext}"
        r2_key = f"projects/{project_request_id}/{stored_name}"

        upload_file_to_r2(
            data=data,
            r2_key=r2_key,
            content_type=file.content_type or "application/octet-stream",
        )

        record = ProjectFile(
            project_request_id=project_request_id,
            filename=file.filename,
            stored_path=f"r2://{r2_key}",
            file_type=file.content_type,
            file_size=len(data),
        )

        db.add(record)
        records.append(record)

    await db.commit()

    for record in records:
        await db.refresh(record)
        response_files.append(
            {
                "id": record.id,
                "filename": record.filename,
            }
        )

    return {
        "status": "ok",
        "files": response_files,
    }