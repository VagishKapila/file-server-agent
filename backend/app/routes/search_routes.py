from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time

from app.db import get_db
from app.models.activity_log import ActivityLog
from app.models.search_result import SearchResult
from app.services.match_engine import search_subcontractors
from app.utils.vendor_guard import clean_vendor_result
from app.routes.activity import log_activity

router = APIRouter()


class SearchRequest(BaseModel):
    project_request_id: int | None = None
    project_id: int | None = None
    category: str | None = None
    tags: list[str] = []
    address: str | None = None
    notes: str | None = None
    email: str | None = None


# 🔥 BACKGROUND SEARCH WORKER
async def background_discovery(
    *,
    project_request_id: int,
    trades: list[str],
    address: str,
    db: AsyncSession,
):
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=address,
        db=db,
    )

    results = results[:10]  # 🔥 HARD CAP

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned or not cleaned.get("phone"):
            continue

        try:
            db.add(
                SearchResult(
                    project_request_id=project_request_id,
                    vendor_name=cleaned["name"],
                    trade=cleaned.get("trade") or trades[0],
                    phone=cleaned.get("phone"),
                    email=cleaned.get("email"),
                    source=cleaned.get("source", "google"),
                )
            )
        except Exception:
            continue

    await db.commit()


@router.post("/search")
async def perform_search(
    data: SearchRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    # -------------------------
    # 0) HARD GUARD
    # -------------------------
    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(400, "project_request_id is required")

    # -------------------------
    # 1) FAST CACHE PATH (<50ms)
    # -------------------------
    existing = await db.execute(
        text("""
            SELECT id, vendor_name, trade, phone, email, source
            FROM search_results
            WHERE project_request_id = :pid
            ORDER BY id DESC
            LIMIT 50
        """),
        {"pid": project_request_id},
    )

    rows = existing.fetchall()
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
                }
                for r in rows
            ],
        }

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
    # 3) FIRE BACKGROUND SEARCH 🔥
    # -------------------------
    background_tasks.add_task(
        background_discovery,
        project_request_id=project_request_id,
        trades=trades,
        address=data.address or "",
        db=db,
    )

    # -------------------------
    # 4) LOG ACTIVITY (FAST)
    # -------------------------
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(project_request_id),
            action="contractor_search_started",
            payload={
                "trade": trades,
                "address": data.address,
                "duration_ms": int((time.time() - t0) * 1000),
            },
        )
    )
    await db.commit()

    await log_activity(
        {
            "user_id": "demo-user",
            "project_id": str(project_request_id),
            "action": "contractor_search_started",
            "payload": {"trade": trades},
        },
        db,
    )

    # -------------------------
    # 5) IMMEDIATE RESPONSE (<100ms)
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": [],  # UI renders instantly
        "message": "Searching contractors… results will appear shortly",
    }