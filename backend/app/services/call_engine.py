# EOF: backend/app/routes/search_routes.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import re
from app.db import get_db
from app.models.search_result import SearchResult
from app.utils.vendor_guard import clean_vendor_result

router = APIRouter()


ALLOW_DISCOVERY = False
if ALLOW_DISCOVERY:
    raise RuntimeError("Discovery is forbidden in call_engine")

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
# CITY NORMALIZATION (robust, human-proof)
# =========================
def extract_city(address: str | None) -> str | None:
    """
    Attempts to extract a usable city token from messy human input.
    Works for:
    - Full addresses
    - City, State
    - No commas
    - Extra words
    """
    if not address:
        return None

    addr = address.lower().strip()

    # Remove zip codes
    addr = re.sub(r"\b\d{5}(-\d{4})?\b", "", addr)

    # Split by commas first
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    if len(parts) >= 2:
        return parts[-2]  # usually city before state

    # Fallback: split by spaces and take last meaningful token
    tokens = [t for t in addr.split() if len(t) > 2]
    if tokens:
        return tokens[-1]

    return None


# =========================
# Search endpoint
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
    if not trades:
        trades = ["General Contractor"]

    trade = trades[0]
    city = extract_city(data.address)

    # -------------------------------------------------
    # 1) SMART DB CACHE (city + trade + score)
    # -------------------------------------------------
    if city:
        cached = await db.execute(
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
                LIMIT 20
            """),
            {
                "city": city,
                "trade": trade,
            },
        )

        rows = cached.fetchall()
        if rows:
            return {
                "status": "ok",
                "project_request_id": project_request_id,
                "vendors": [
                    {
                        "id": r.id,
                        "vendor_name": r.vendor_name,
                        "trade": r.trade,
                        "phone": r.phone,
                        "email": r.email,
                        "source": r.source,
                        "score": float(r.score),
                    }
                    for r in rows
                ],
                "cache_mode": "city_score_ranked",
                "duration_ms": int((time.time() - t0) * 1000),
            }

    # -------------------------------------------------
    # 2) SLOW PATH (FIRST-TIME CITY DISCOVERY ONLY)
    # Google / Yelp hit happens HERE
    # -------------------------------------------------
    results = await search_subcontractors(
        trades=[trade],
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    results = results[:5]  # UI-first, speed-first

    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned or not cleaned.get("phone"):
            continue

        try:
            sr = SearchResult(
                project_request_id=project_request_id,
                vendor_name=cleaned["name"],
                trade=trade,
                phone=cleaned.get("phone"),
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
            db.add(sr)
            saved += 1

            # Initialize vendor score row if missing
            if city:
                await db.execute(
                    text("""
                        INSERT INTO vendor_scores
                          (vendor_phone, vendor_name, trade, city, score)
                        VALUES
                          (:phone, :name, :trade, :city, 0)
                        ON CONFLICT (vendor_phone, trade, city)
                        DO NOTHING
                    """),
                    {
                        "phone": cleaned.get("phone"),
                        "name": cleaned["name"],
                        "trade": trade,
                        "city": city,
                    },
                )

        except Exception:
            continue

    await db.commit()

    # -------------------------------------------------
    # 3) RETURN WHAT WE JUST SAVED (UI NEEDS IT NOW)
    # -------------------------------------------------
    rows2 = await db.execute(
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
            WHERE sr.project_request_id = :pid
            ORDER BY score DESC, sr.id DESC
            LIMIT 20
        """),
        {
            "pid": project_request_id,
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
        for r in rows2.fetchall()
    ]

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": vendors,
        "saved_results": saved,
        "cache_mode": "fresh_city_seed",
        "duration_ms": int((time.time() - t0) * 1000),
    }