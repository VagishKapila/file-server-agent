from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


async def is_global_material_outreach_enabled(
    db: AsyncSession,
) -> bool:
    result = await db.execute(
        text("""
            SELECT value
            FROM system_settings
            WHERE key = 'GLOBAL_MATERIAL_OUTREACH'
            LIMIT 1
        """)
    )
    row = result.mappings().first()
    return bool(row and row["value"].lower() == "true")