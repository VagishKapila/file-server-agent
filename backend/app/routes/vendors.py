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

    # US formats
    if digits.startswith("+1") or (len(digits) == 10 and digits.isdigit()):
        return "USA"

    # India
    if digits.startswith("+91") or (len(digits) == 10 and digits[0] in "987"):
        return "India"

    # UK
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
# GET preferred vendors
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
# CORS preflight
# ---------------------------------------------------------
@router.options("/add")
async def options_add():
    return Response(status_code=200)


# ---------------------------------------------------------
# ADD vendor + activity log
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

    await db.execute(
        text("""
            INSERT INTO activity_log (user_id, project_id, action, payload, created_at)
            VALUES (:user_id, :project_id, :action, :payload, :created_at)
        """),
        {
            "user_id": data.user_id,
            "project_id": None,
            "action": "vendor_added",
            "payload": json.dumps({
                "vendor_id": row["id"],
                "name": row["name"],
                "trade": row["trade"],
                "city": row["city"],
                "state": row["state"],
                "country": row["country"],
            }),
            "created_at": datetime.utcnow(),
        },
    )

    await db.commit()
    return dict(row)


# ---------------------------------------------------------
# REMOVE vendor + activity log
# ---------------------------------------------------------
@router.post("/remove")
async def remove_vendor(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    vendor_id = payload.get("id")
    user_id = payload.get("user_id")

    if not vendor_id:
        raise HTTPException(status_code=400, detail="Missing vendor id")

    result = await db.execute(
        text("""
            SELECT id, name, trade
            FROM preferred_vendors
            WHERE id = :id
        """),
        {"id": vendor_id},
    )

    vendor = result.mappings().first()

    if vendor:
        await db.execute(
            text("""
                INSERT INTO activity_log (user_id, project_id, action, payload, created_at)
                VALUES (:user_id, :project_id, :action, :payload, :created_at)
            """),
            {
                "user_id": user_id,
                "project_id": None,
                "action": "vendor_removed",
                "payload": json.dumps({
                    "vendor_id": vendor["id"],
                    "name": vendor["name"],
                    "trade": vendor["trade"],
                }),
                "created_at": datetime.utcnow(),
            },
        )

    await db.execute(
        text("DELETE FROM preferred_vendors WHERE id = :id"),
        {"id": vendor_id},
    )

    await db.commit()
    return {"status": "deleted", "id": vendor_id}


# ---------------------------------------------------------
# AUTOCOMPLETE SEARCH
# ---------------------------------------------------------
@router.get("/search")
async def search_vendor_names(
    q: str = "",
    db: AsyncSession = Depends(get_db),
):
    q = q.strip().lower()
    if len(q) < 2:
        return []

    pattern = f"%{q}%"

    result = await db.execute(
        text("""
            SELECT id, name, trade, city, state, country
            FROM preferred_vendors
            WHERE LOWER(name) LIKE :pattern
            ORDER BY name ASC
            LIMIT 15
        """),
        {"pattern": pattern},
    )

    return [dict(row) for row in result.mappings().all()]