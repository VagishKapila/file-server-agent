from fastapi import APIRouter, Depends, Body
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.project import ProjectRequest

router = APIRouter(prefix="/project-requests", tags=["Project Requests"])


@router.post("/", status_code=200)
async def create_project_request(
    payload: dict = Body(...),
    db: AsyncSession = Depends(get_db),
):
    pr = ProjectRequest(
        project_name=payload["project_name"],
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