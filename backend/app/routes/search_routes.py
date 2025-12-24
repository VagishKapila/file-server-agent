from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..services.match_engine import search_subcontractors
from ..db import get_db
from ..models.activity_log import ActivityLog
from ..models.search_result import SearchResult
from .activity import log_activity

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
    email: str | None = None   # ✅ ADD THIS


# =========================
# Search endpoint
# =========================
@router.post("/search")
async def perform_search(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    # =========================
    # 0) HARD GUARANTEE: Project exists (NO ORM IMPORT)
    # =========================
    result = await db.execute(
        text("SELECT id FROM project_requests WHERE id = :id"),
        {"id": data.project_request_id},
    )
    project_row = result.first()

    if not project_row:
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
        await db.flush()  # FK safety

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
    # 2) Run Google search (phones REQUIRED)
    # =========================
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
    )

    # =========================
    # 3) Persist results (phones are the product)
    # =========================
    for r in results:
        if not r.get("phone"):
            continue  # irrelevant without phone

        db.add(
            SearchResult(
                project_request_id=data.project_request_id,
                vendor_name=r.get("name"),
                trade=r.get("trade") or trades[0],
                phone=r.get("phone"),
                email=r.get("email"),
                source=r.get("source", "google"),
            )
        )

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
                "results_count": len(results),
            },
        )
    )

    # =========================
    # 5) Commit ONCE (atomic)
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
                "results_count": len(results),
            },
        },
        db,
    )

    # =========================
    # 7) Optional client email (reuse existing route)
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
        "results": results,
    }

    