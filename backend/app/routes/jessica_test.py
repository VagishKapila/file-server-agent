from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime

from ..db import get_db
from ..models.activity_log import ActivityLog

router = APIRouter(prefix="/jessica/test", tags=["jessica-test"])


# ---------------------------------------------------------
# Schemas
# ---------------------------------------------------------

class TestModeIn(BaseModel):
    enabled: bool


class TestNumbersIn(BaseModel):
    numbers: list[str]


# ---------------------------------------------------------
# Toggle test mode
# ---------------------------------------------------------
@router.post("/mode", response_model=None)
async def set_test_mode(
    data: TestModeIn,
    db: AsyncSession = Depends(get_db),
):
    db.add(
        ActivityLog(
            user_id="system",
            project_id=None,
            action="jessica_test_mode_changed",
            payload={"enabled": data.enabled},
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()

    return {"status": "ok", "enabled": data.enabled}


# ---------------------------------------------------------
# Update test numbers
# ---------------------------------------------------------
@router.post("/numbers", response_model=None)
async def set_test_numbers(
    data: TestNumbersIn,
    db: AsyncSession = Depends(get_db),
):
    db.add(
        ActivityLog(
            user_id="system",
            project_id=None,
            action="jessica_test_numbers_updated",
            payload={"numbers": data.numbers},
            created_at=datetime.utcnow(),
        )
    )
    await db.commit()

    return {"status": "ok", "numbers": data.numbers}


# ---------------------------------------------------------
# Get current test status (FIXED)
# ---------------------------------------------------------
@router.get("/status", response_model=None)
async def get_test_status(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text(
            """
            SELECT action, payload, created_at
            FROM activity_log
            WHERE action IN (
                'jessica_test_mode_changed',
                'jessica_test_numbers_updated'
            )
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
    )

    rows = result.fetchall()

    return [
        {
            "action": r[0],
            "payload": r[1],
            "created_at": r[2],
        }
        for r in rows
    ]