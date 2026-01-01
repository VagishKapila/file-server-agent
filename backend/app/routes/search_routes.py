from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..services.match_engine import search_subcontractors
from ..services.google_scraper import google_search
from ..db import get_db
from ..models.activity_log import ActivityLog
from ..models.search_result import SearchResult
from .activity import log_activity
from app.utils.vendor_guard import clean_vendor_result

router = APIRouter()


# =========================
# Request schema
# =========================
class SearchRequest(BaseModel):
    project_request_id: int
    category: str | None = None
    tags: list[str] = []
    address: str | None = None
    notes: str | None = None
    email: str | None = None


# =========================
# Search endpoint
# =========================
@router.post("/search")
async def perform_search(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    # -------------------------
    # 0) Ensure project exists
    # -------------------------
    result = await db.execute(
        text("SELECT id FROM project_requests WHERE id = :id"),
        {"id": data.project_request_id},
    )

    if not result.first():
        await db.execute(
            text("""
                INSERT INTO project_requests (id, project_name, location, request_type)
                VALUES (:id, :name, :location, :type)
            """),
            {
                "id": data.project_request_id,
                "name": "Auto-created from contractor search",
                "location": data.address or "Unknown",
                "type": "subs",
            },
        )
        await db.commit()

    # -------------------------
    # 1) Normalize trades
    # -------------------------
    trades: list[str] = []

    if data.category and data.category.strip():
        trades.append(data.category.strip())

    for tag in data.tags:
        if tag and tag.strip():
            trades.append(tag.strip())

    if not trades:
        trades = ["General Contractor"]

    # -------------------------
    # 2) Primary search engine
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="50",
        preferred=[],
        location=data.address or "",
        db=db,   # ✅ pass injected session through
    )

    # -------------------------
    # 3) HARD GUARANTEE: Google fallback
    # -------------------------
    if not results:
        raw = google_search(
            trades=trades,
            location=data.address or "",
            radius_meters=80467,  # ~50 miles
        )

        results = [
            {
                "name": r.get("name"),
                "phone": r.get("phone"),
                "city": r.get("city"),
                "preferred": False,
                "same_city": False,
                "source": "google",
            }
            for r in raw
            if r.get("phone")
        ]

    # -------------------------
    # 4) Persist CLEAN results
    # -------------------------
    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned:
            continue

        db.add(
            SearchResult(
                project_request_id=data.project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned.get("trade") or trades[0],
                phone=cleaned["phone"],
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
        )
        saved += 1

    # -------------------------
    # 5) Activity log
    # -------------------------
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(data.project_request_id),
            action="contractor_search",
            payload={
                "trade": trades,
                "address": data.address,
                "raw_results": len(results),
                "saved_results": saved,
            },
        )
    )

    await db.commit()

    # -------------------------
    # 6) Async feed
    # -------------------------
    await log_activity(
        {
            "user_id": "demo-user",
            "project_id": str(data.project_request_id),
            "action": "contractor_search",
            "payload": {
                "trade": trades,
                "saved_results": saved,
            },
        },
        db,
    )

    return {
        "results": results,
        "raw_results": len(results),
        "saved_results": saved,
    }