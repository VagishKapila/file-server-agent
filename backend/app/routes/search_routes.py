from fastapi import APIRouter, Depends, HTTPException
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
# Search endpoint
# =========================
@router.post("/search")
async def perform_search(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    # -------------------------
    # 0) HARD GUARD
    # -------------------------
    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(
            status_code=400,
            detail="project_request_id is required",
        )

    # -------------------------
    # 1) FAST PATH — DB CACHE
    # -------------------------
    existing = await db.execute(
        text("""
            SELECT
                id,
                vendor_name,
                trade,
                phone,
                email,
                source
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
            "raw_results": len(rows),
            "saved_results": len(rows),
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
    # 2) Ensure project exists
    # -------------------------
    result = await db.execute(
        text("SELECT id FROM project_requests WHERE id = :id"),
        {"id": project_request_id},
    )

    if not result.first():
        await db.execute(
            text("""
                INSERT INTO project_requests (id, project_name, location, request_type)
                VALUES (:id, :name, :location, :type)
            """),
            {
                "id": project_request_id,
                "name": "Auto-created from contractor search",
                "location": data.address or "Unknown",
                "type": "subs",
            },
        )
        await db.commit()

    # -------------------------
    # 3) Normalize trades
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
    # 4) Run discovery engine
    # ⚠️ HARD CAP to prevent slowdown
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    results = results[:10]  # 🔥 SPEED CAP

    # -------------------------
    # 5) Persist clean results
    # -------------------------
    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned or not cleaned.get("phone"):
            continue

        cleaned.pop("callable", None)
        cleaned.pop("confidence", None)
        cleaned.pop("score", None)

        try:
            sr = SearchResult(
                project_request_id=project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned.get("trade") or trades[0],
                phone=cleaned.get("phone"),
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
            db.add(sr)
            await db.flush()
            saved += 1
        except Exception:
            continue

    # -------------------------
    # 6) Fetch for UI
    # -------------------------
    rows = await db.execute(
        text("""
            SELECT
                id,
                vendor_name,
                trade,
                phone,
                email,
                source
            FROM search_results
            WHERE project_request_id = :pid
            ORDER BY id DESC
            LIMIT 50
        """),
        {"pid": project_request_id},
    )

    vendors = [
        {
            "id": r.id,
            "vendor_name": r.vendor_name,
            "trade": r.trade,
            "phone": r.phone,
            "email": r.email,
            "source": r.source,
        }
        for r in rows.fetchall()
    ]

    # -------------------------
    # 7) Activity log
    # -------------------------
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(project_request_id),
            action="contractor_search",
            payload={
                "trade": trades,
                "address": data.address,
                "saved_results": saved,
                "duration_ms": int((time.time() - t0) * 1000),
            },
        )
    )

    await db.commit()

    await log_activity(
        {
            "user_id": "demo-user",
            "project_id": str(project_request_id),
            "action": "contractor_search",
            "payload": {
                "trade": trades,
                "saved_results": saved,
            },
        },
        db,
    )

    # -------------------------
    # 8) Final response
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "raw_results": len(results),
        "saved_results": saved,
        "vendors": vendors,
    }