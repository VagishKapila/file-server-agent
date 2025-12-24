from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db import get_db
from app.models.beta_subscriber import BetaSubscriber

router = APIRouter(prefix="/admin/beta", tags=["beta"])

@router.get("/")
async def list_beta_subscribers(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(BetaSubscriber).order_by(BetaSubscriber.created_at.desc())
    )
    return rows.scalars().all()

@router.post("/")
async def add_beta_subscriber(data: dict, db: AsyncSession = Depends(get_db)):
    sub = BetaSubscriber(**data)
    db.add(sub)
    await db.commit()
    return {"ok": True}

@router.patch("/{sub_id}")
async def update_beta_subscriber(sub_id: int, data: dict, db: AsyncSession = Depends(get_db)):
    row = await db.execute(
        select(BetaSubscriber).where(BetaSubscriber.id == sub_id)
    )
    sub = row.scalar_one()
    for k, v in data.items():
        setattr(sub, k, v)
    await db.commit()
    return {"ok": True}
