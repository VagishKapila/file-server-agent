from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.user_profile import UserProfile

router = APIRouter(prefix="/users/profile", tags=["user-profile"])

@router.post("/callback")
async def save_callback(info: dict, db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(UserProfile).limit(1))
    profile = row.scalar_one_or_none()

    if not profile:
        profile = UserProfile()

    profile.name = info.get("name")
    profile.email = info.get("email")
    profile.phone = info.get("phone")

    db.add(profile)
    await db.commit()
    return {"ok": True}

@router.get("/callback")
async def get_callback(db: AsyncSession = Depends(get_db)):
    row = await db.execute(select(UserProfile).limit(1))
    profile = row.scalar_one_or_none()

    if not profile:
        return {}

    return {
        "name": profile.name,
        "email": profile.email,
        "phone": profile.phone,
    }
