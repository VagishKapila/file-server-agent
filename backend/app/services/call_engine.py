# EOF: backend/app/routes/search_routes.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import re

from app.db import get_db

router = APIRouter()


# =========================
# Request schema
# =========================
class SearchRequest(BaseModel):
    project_request_id: int | None = None
    project_id: int | None = None
    category: str | None = None
    tags: list[str] = []
    address: str | None = None
    notes: str | None = None
    email: str | None = None


# =========================
# CITY NORMALIZATION
# =========================
def extract_city(address: str | None) -> str | None:
    if not address:
        return None

    addr = address.lower().strip()
    addr = re.sub(r"\b\d{5}(-\d{4})?\b", "", addr)

    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-2]

    tokens = [t for t in addr.split() if len(t) > 2]
    return tokens[-1] if tokens else None


# =========================
# Search endpoint (DB ONLY)
# =========================
@router.post("/search")
async def perform_search(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(status_code=400, detail="project_request_id is required")

    # Normalize trade
    trades: list[str] = []
    if data.category and data.category.strip():
        trades.append(data.category.strip())
    for tag in data.tags:
        if tag and tag.strip():
            trades.append(tag.strip())

    trade = trades[0] if trades else "General Contractor"
    city = extract_city(data.address)

    if not city:
        return {
            "status": "ok",
            "project_request_id": project_request_id,
            "vendors": [],
            "message": "City not resolved",
            "duration_ms": int((time.time() - t0) * 1000),
        }

    # -------------------------------------------------
    # DB-ONLY ranked fetch (NO DISCOVERY)
    # -------------------------------------------------
    result = await db.execute(
        text("""
            SELECT
                sr.id,
                sr.vendor_name,
                sr.trade,
                sr.phone,
                sr.email,
                sr.source,
                COALESCE(vs.score, 0) AS score
            FROM search_results sr
            LEFT JOIN vendor_scores vs
              ON vs.vendor_phone = sr.phone
             AND vs.trade = sr.trade
             AND vs.city = :city
            WHERE sr.trade = :trade
              AND sr.phone IS NOT NULL
            ORDER BY
              COALESCE(vs.score, 0) DESC,
              sr.id DESC
            LIMIT 5
        """),
        {
            "trade": trade,
            "city": city,
        },
    )

    vendors = [
        {
            "id": r.id,
            "vendor_name": r.vendor_name,
            "trade": r.trade,
            "phone": r.phone,
            "email": r.email,
            "source": r.source,
            "score": float(r.score),
        }
        for r in result.fetchall()
    ]

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": vendors,
        "cache_mode": "db_only_ranked",
        "duration_ms": int((time.time() - t0) * 1000),
    }