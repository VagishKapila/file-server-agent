from app.db import database

async def is_global_material_outreach_enabled() -> bool:
    row = await database.fetch_one("""
        SELECT value FROM system_settings
        WHERE key = 'GLOBAL_MATERIAL_OUTREACH'
        LIMIT 1
    """)
    return row and row["value"].lower() == "true"

async def set_global_material_outreach(enabled: bool):
    await database.execute("""
        INSERT INTO system_settings (key, value)
        VALUES ('GLOBAL_MATERIAL_OUTREACH', :value)
        ON CONFLICT (key)
        DO UPDATE SET value = :value, updated_at = NOW()
    """, {"value": "true" if enabled else "false"})
