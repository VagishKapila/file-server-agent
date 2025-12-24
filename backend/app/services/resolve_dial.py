from sqlalchemy.ext.asyncio import AsyncSession

async def resolve_dial_number(real_number: str, db: AsyncSession) -> str:
    return real_number