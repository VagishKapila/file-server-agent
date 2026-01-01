from fastapi import APIRouter, Depends, Body
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.db import get_db
from app.models.project import ProjectRequest

router = APIRouter(
    prefix="/project-requests",
    tags=["Project Requests"]
)

@router.post("/", status_code=200)
async def create_project_request(
    payload: Dict[str, Any] = Body(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Creates a new ProjectRequest row.

    Expected payload (minimum):
      {
        "project_name": "My Project",
        "location": "San Jose, CA",
        "request_type": "sub"   # optional
      }
    """

    project_name = payload.get("project_name")
    if not project_name:
        # Keep it simple; frontend should always send project_name
        # but this prevents silent crashes.
        return {"error": "project_name is required"}

    pr = ProjectRequest(
        project_name=project_name,
        location=payload.get("location"),
        request_type=payload.get("request_type", "sub"),
    )

    db.add(pr)
    await db.flush()
    await db.refresh(pr)
    await db.commit()

    return {
        "project_request_id": pr.id,
        "project_name": pr.project_name,
        "location": pr.location,
        "request_type": pr.request_type,
    }