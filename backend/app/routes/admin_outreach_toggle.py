from fastapi import APIRouter
from app.db import database

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/global-material-outreach")
async def get_global_outreach_state():
    row = await database.fetch_one("""
        SELECT value FROM system_settings
        WHERE key = 'GLOBAL_MATERIAL_OUTREACH'
        LIMIT 1
    """)
    return {
        "GLOBAL_MATERIAL_OUTREACH": row["value"] if row else "false"
    }


@router.post("/global-material-outreach/{state}")
async def set_global_outreach_state(state: str):
    state = state.lower()
    if state not in ("on", "off"):
        return {"error": "state must be 'on' or 'off'"}

    value = "true" if state == "on" else "false"

    await database.execute("""
        INSERT INTO system_settings (key, value)
        VALUES ('GLOBAL_MATERIAL_OUTREACH', :value)
        ON CONFLICT (key)
        DO UPDATE SET value = :value, updated_at = NOW()
    """, {"value": value})

    return {
        "GLOBAL_MATERIAL_OUTREACH": value
    }
