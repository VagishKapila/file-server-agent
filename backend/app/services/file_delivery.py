from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.project_files import ProjectFile

EMAIL_ATTACHMENT_LIMIT_MB = 20


async def prepare_files_for_vendor(
    project_request_id: int,
    db: AsyncSession,
) -> Dict:
    """
    Decide attach vs link.
    ALWAYS preserve r2:// paths for email delivery.
    """

    res = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == project_request_id)
    )
    files: List[ProjectFile] = res.scalars().all()

    if not files:
        return {
            "mode": "none",
            "files": [],
        }

    total_bytes = sum(f.file_size or 0 for f in files)
    total_mb = total_bytes / (1024 * 1024)

    payload = []

    for f in files:
        payload.append({
            "filename": f.filename,
            "r2_path": f.stored_path if f.stored_path.startswith("r2://") else None,
            "size": f.file_size,
        })

    if total_mb <= EMAIL_ATTACHMENT_LIMIT_MB:
        return {
            "mode": "attach",
            "total_mb": round(total_mb, 2),
            "files": payload,
        }

    return {
        "mode": "link",
        "total_mb": round(total_mb, 2),
        "files": payload,
    }