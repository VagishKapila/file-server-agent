from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db
from app.models.activity_log import ActivityLog
from app.models.search_result import SearchResult
from app.services.match_engine import search_subcontractors
from app.utils.vendor_guard import clean_vendor_result
from app.routes.activity import log_activity

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
    # 0) HARD GUARD
    # -------------------------
    if not data.project_request_id:
        raise HTTPException(
            status_code=400,
            detail="project_request_id is required",
        )

    # -------------------------
    # 1) Ensure project exists
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
    # 2) Normalize trades
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
    # 3) Run search engine
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    # -------------------------
    # 4) Persist CLEAN results
    # -------------------------
    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned:
            continue

        # 🔥 ABSOLUTE SAFETY: strip non-DB keys
        cleaned.pop("callable", None)
        cleaned.pop("confidence", None)
        cleaned.pop("score", None)

        db.add(
            SearchResult(
                project_request_id=data.project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned.get("trade") or trades[0],
                phone=cleaned.get("phone"),
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
    # 6) Async activity feed
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
        "status": "ok",
        "project_request_id": data.project_request_id,
        "raw_results": len(results),
        "saved_results": saved,
    }