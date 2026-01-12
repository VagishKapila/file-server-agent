from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/global-material-outreach")
async def get_global_outreach_state(
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT value
            FROM system_settings
            WHERE key = 'GLOBAL_MATERIAL_OUTREACH'
            LIMIT 1
        """)
    )
    row = result.mappings().first()

    return {
        "GLOBAL_MATERIAL_OUTREACH": row["value"] if row else "false"
    }


@router.post("/global-material-outreach/{state}")
async def set_global_outreach_state(
    state: str,
    db: AsyncSession = Depends(get_db),
):
    state = state.lower()
    if state not in ("on", "off"):
        return {"error": "state must be 'on' or 'off'"}

    value = "true" if state == "on" else "false"

    await db.execute(
        text("""
            INSERT INTO system_settings (key, value)
            VALUES ('GLOBAL_MATERIAL_OUTREACH', :value)
            ON CONFLICT (key)
            DO UPDATE SET value = :value, updated_at = NOW()
        """),
        {"value": value},
    )
    await db.commit()

    return {"GLOBAL_MATERIAL_OUTREACH": value}