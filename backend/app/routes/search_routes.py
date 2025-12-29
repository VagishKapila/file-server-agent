from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..services.match_engine import search_subcontractors
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
    # =========================
    # 0) HARD GUARANTEE: Project exists
    # =========================
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
        await db.flush()

    # =========================
    # 1) Normalize trades
    # =========================
    trades: list[str] = []

    if data.category and data.category.strip():
        trades.append(data.category.strip())

    for tag in data.tags:
        if tag and tag.strip():
            trades.append(tag.strip())

    if not trades:
        trades = ["General Contractor"]

    # =========================
    # 2) Run search
    # =========================
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
    )

    # =========================
    # 3) Persist CLEAN results only
    # =========================
    cleaned_count = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned:
            continue

        db.add(
            SearchResult(
                project_request_id=data.project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned["trade"] or trades[0],
                phone=cleaned["phone"],        # ALWAYS E.164 now
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
        )
        cleaned_count += 1

    # =========================
    # 4) Activity log
    # =========================
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(data.project_request_id),
            action="contractor_search",
            payload={
                "trade": trades,
                "address": data.address,
                "raw_results": len(results),
                "saved_results": cleaned_count,
            },
        )
    )

    # =========================
    # 5) Commit ONCE
    # =========================
    await db.commit()

    # =========================
    # 6) Async activity feed
    # =========================
    await log_activity(
        {
            "user_id": "demo-user",
            "project_id": str(data.project_request_id),
            "action": "contractor_search",
            "payload": {
                "trade": trades,
                "saved_results": cleaned_count,
            },
        },
        db,
    )

    # =========================
    # 7) Optional client email
    # =========================
    if data.email:
        from app.routes.client_email import (
            send_client_summary_email,
            ClientEmailRequest,
        )

        await send_client_summary_email(
            payload=ClientEmailRequest(
                project_request_id=data.project_request_id,
                client_email=data.email,
            ),
            db=db,
        )

    return {
        "status": "ok",
        "project_request_id": data.project_request_id,
        "raw_results": len(results),
        "saved_results": cleaned_count,
    }