from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..db import get_db
from ..models.activity_log import ActivityLog

router = APIRouter(prefix="/activity", tags=["activity"])

@router.post("/log")
async def log_activity(data: dict, db: AsyncSession = Depends(get_db)):
    entry = ActivityLog(
        user_id=data.get("user_id"),
        project_id=data.get("project_id"),
        action=data.get("action"),
        payload=data.get("payload"),
    )
    db.add(entry)
    await db.commit()
    return {"status": "ok"}

@router.get("/list")
async def list_activity(limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(limit)
    )
    return result.scalars().all()
