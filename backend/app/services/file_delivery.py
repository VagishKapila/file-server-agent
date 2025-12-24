from typing import List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os

from backend.app.models.project_files import ProjectFile

# -----------------------------------
# CONFIG
# -----------------------------------

EMAIL_ATTACHMENT_LIMIT_MB = 20

# Public file server base
# Railway example:
# https://file-server-agent-production.up.railway.app
FILE_SERVER_BASE_URL = os.getenv(
    "FILE_SERVER_BASE_URL",
    "http://localhost:8000"
)

# -----------------------------------
# MAIN FUNCTION
# -----------------------------------

async def prepare_files_for_vendor(
    project_request_id: int,
    db: AsyncSession,
) -> Dict:
    """
    Decide whether files should be attached or sent as links.
    Returns normalized metadata for email / AI agent.
    """

    stmt = select(ProjectFile).where(
        ProjectFile.project_request_id == project_request_id
    )
    res = await db.execute(stmt)
    files: List[ProjectFile] = res.scalars().all()

    if not files:
        return {
            "mode": "none",
            "files": [],
        }

    total_bytes = sum(f.file_size or 0 for f in files)
    total_mb = total_bytes / (1024 * 1024)

    file_payload = []

    for f in files:
        # Normalize stored path → public URL
        # Example stored_path:
        # uploads/projects/203/abc.pdf
        public_url = f"{FILE_SERVER_BASE_URL}/files/{f.stored_path}"

        file_payload.append({
            "filename": f.filename,
            "stored_path": f.stored_path,
            "public_url": public_url,
            "size": f.file_size,
        })

    # -----------------------------------
    # ATTACH MODE
    # -----------------------------------
    if total_mb <= EMAIL_ATTACHMENT_LIMIT_MB:
        return {
            "mode": "attach",
            "total_mb": round(total_mb, 2),
            "files": file_payload,
        }

    # -----------------------------------
    # LINK MODE
    # -----------------------------------
    return {
        "mode": "link",
        "total_mb": round(total_mb, 2),
        "files": file_payload,
    }