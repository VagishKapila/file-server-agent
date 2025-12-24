from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.db import get_db
from app.models.materials import (
    MaterialVendor,
    MaterialOutreach,
    MaterialQuote,
)

router = APIRouter(prefix="/material-calls", tags=["Material Calls"])


class MaterialCallPayload(BaseModel):
    project_request_id: int
    material_category: str

    vendor_name: str
    phone: str | None = None
    email: str | None = None

    price: float | None = None
    currency: str | None = "USD"
    lead_time_days: int | None = None

    confirmed: bool = False
    ai_summary: str | None = None
    extra_notes: str | None = None


@router.post("/")
async def save_material_call(
    payload: MaterialCallPayload,
    db: AsyncSession = Depends(get_db),
):
    # 1️⃣ Find or create vendor
    stmt = select(MaterialVendor).where(
        MaterialVendor.company_name == payload.vendor_name
    )
    res = await db.execute(stmt)
    vendor = res.scalar_one_or_none()

    if not vendor:
        vendor = MaterialVendor(
            company_name=payload.vendor_name,
            phone=payload.phone,
            email=payload.email,
        )
        db.add(vendor)
        await db.flush()

    # 2️⃣ Prevent duplicate confirmed outreach
    stmt = select(MaterialOutreach).where(
        MaterialOutreach.project_request_id == payload.project_request_id,
        MaterialOutreach.material_vendor_id == vendor.id,  # 🔴 FIXED
        MaterialOutreach.material_category == payload.material_category,
        MaterialOutreach.status == "confirmed",
    )
    res = await db.execute(stmt)
    existing = res.scalar_one_or_none()

    if existing:
        return {
            "status": "ignored",
            "reason": "already_confirmed",
            "outreach_id": existing.id,
        }

    # 3️⃣ Create outreach
    outreach = MaterialOutreach(
        project_request_id=payload.project_request_id,
        material_vendor_id=vendor.id,  # 🔴 FIXED
        material_category=payload.material_category,
        status="confirmed" if payload.confirmed else "declined",
        confirmed_at=datetime.utcnow() if payload.confirmed else None,
        ai_summary=payload.ai_summary,
    )
    db.add(outreach)
    await db.flush()

    # 4️⃣ Create quote
    quote = MaterialQuote(
        outreach_id=outreach.id,
        price=payload.price,
        currency=payload.currency,
        lead_time_days=payload.lead_time_days,
        structured_payload=payload.dict(),
    )
    db.add(quote)

    await db.commit()

    return {
        "status": outreach.status,
        "vendor_id": vendor.id,
        "outreach_id": outreach.id,
        "confirmed_at": outreach.confirmed_at,
    }