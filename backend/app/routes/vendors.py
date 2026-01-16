from fastapi import APIRouter, HTTPException, Response, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import json

from ..db import get_db

router = APIRouter(prefix="/vendors", tags=["vendors"])

# ---------------------------------------------------------
# Utility: detect country from phone number
# ---------------------------------------------------------
def detect_country_from_phone(phone: str | None):
    if not phone:
        return "USA"

    digits = phone.replace(" ", "").replace("-", "").strip()

    if digits.startswith("+1") or (len(digits) == 10 and digits.isdigit()):
        return "USA"

    if digits.startswith("+91") or (len(digits) == 10 and digits[0] in "987"):
        return "India"

    if digits.startswith("+44"):
        return "United Kingdom"

    return "USA"


# ---------------------------------------------------------
# Pydantic model incoming
# ---------------------------------------------------------
class VendorIn(BaseModel):
    user_id: str
    name: str
    phone: str | None = None
    trade: str | None = None
    city: str | None = None
    state: str | None = ""
    country: str | None = "USA"


# ---------------------------------------------------------
# Normalize city, state, country
# ---------------------------------------------------------
def normalize_location(city: str | None, state: str | None, country: str | None):
    city = (city or "").strip()
    state = (state or "").strip()
    country = (country or "").strip() if country else "USA"

    known_map = {
        "san jose": ("CA", "USA"),
        "fremont": ("CA", "USA"),
        "oakland": ("CA", "USA"),
        "san francisco": ("CA", "USA"),
        "toronto": ("ON", "Canada"),
        "vancouver": ("BC", "Canada"),
    }

    key = city.lower()
    if key in known_map:
        state, country = known_map[key]

    return city, state, country


# ---------------------------------------------------------
# API: GET preferred vendors
# ---------------------------------------------------------
@router.get("/")
async def get_preferred(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("""
            SELECT id, user_id, name, phone, trade, city, state, country, created_at
            FROM preferred_vendors
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user_id},
    )

    return [dict(row) for row in result.mappings().all()]


# ---------------------------------------------------------
# API: ADD vendor
# ---------------------------------------------------------
@router.post("/add")
async def add_vendor(
    data: VendorIn,
    db: AsyncSession = Depends(get_db),
):
    city, state, normalized_country = normalize_location(
        data.city, data.state, data.country
    )
    country = detect_country_from_phone(data.phone) or normalized_country

    result = await db.execute(
        text("""
            INSERT INTO preferred_vendors (user_id, name, phone, trade, city, state, country)
            VALUES (:user_id, :name, :phone, :trade, :city, :state, :country)
            RETURNING id, user_id, name, phone, trade, city, state, country, created_at
        """),
        {
            "user_id": data.user_id,
            "name": data.name,
            "phone": data.phone,
            "trade": data.trade,
            "city": city,
            "state": state,
            "country": country,
        },
    )

    row = result.mappings().first()
    if not row:
        raise HTTPException(status_code=500, detail="Vendor insert failed")

    await db.commit()
    return dict(row)


# ---------------------------------------------------------
# SERVICE HELPER (✅ THIS FIXES THE CRASH)
# ---------------------------------------------------------
async def get_preferred_vendors_for_user(
    db: AsyncSession,
    user_id: int,
):
    """
    Internal service helper.
    Safe to import into orchestrators.
    """
    result = await db.execute(
        text("""
            SELECT id, name, phone, trade, city, state, country
            FROM preferred_vendors
            WHERE user_id = :user_id
            ORDER BY created_at DESC
        """),
        {"user_id": user_id},
    )

    return [dict(row) for row in result.mappings().all()]