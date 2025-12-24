from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from modules.vendors.models.vendor import Vendor

router = APIRouter(prefix="/vendors", tags=["vendors"])

# ----------------------
# SAVE VENDOR
# ----------------------
@router.post("/save")
async def save_vendor(vendor: dict, db: AsyncSession = Depends(get_db)):
    new_v = Vendor(
        name=vendor.get("name"),
        company=vendor.get("company"),
        trade=vendor.get("trade"),
        phone=vendor.get("phone"),
        city=vendor.get("city"),
        country=vendor.get("country"),
        created_by="123"
    )
    db.add(new_v)
    await db.commit()
    await db.refresh(new_v)
    return {"status": "ok", "vendor": new_v.id}

# ----------------------
# LIST VENDORS
# ----------------------
@router.get("/list")
async def list_vendors(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Vendor))
    return result.scalars().all()