from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.user import User

router = APIRouter(prefix="/auth/google", tags=["auth"])

@router.post("/login")
async def google_login(payload: dict, db: AsyncSession = Depends(get_db)):
    email = payload.get("email")
    name = payload.get("name")
    picture = payload.get("picture")
    google_sub = payload.get("sub")

    if not email or not google_sub:
        raise HTTPException(status_code=400, detail="Invalid Google payload")

    result = await db.execute(select(User).where(User.google_sub == google_sub))
    user = result.scalar_one_or_none()

    if not user:
        user = User(
            email=email,
            name=name,
            picture=picture,
            google_sub=google_sub,
            provider="google",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
    }
