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
# Background enrichment
# =========================
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
            await db.flush()
        except Exception:
            continue

    await db.commit()


# =========================
# Search endpoint
# =========================
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
        raise HTTPException(status_code=400, detail="project_request_id is required")

    # -------------------------
    # 1) FAST DB CACHE (instant)
    # -------------------------
    cached = await db.execute(
        text("""
            SELECT id, vendor_name, trade, phone, email, source
            FROM search_results
            WHERE project_request_id = :pid
            ORDER BY id DESC
            LIMIT 50
        """),
        {"pid": project_request_id},
    )

    rows = cached.fetchall()
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
    exists = await db.execute(
        text("SELECT id FROM project_requests WHERE id = :id"),
        {"id": project_request_id},
    )

    if not exists.first():
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
    if data.category:
        trades.append(data.category.strip())
    trades.extend([t.strip() for t in data.tags if t.strip()])
    if not trades:
        trades = ["General Contractor"]

    # -------------------------
    # 4) FAST DISCOVERY (UI GUARANTEE)
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    # 🔥 GUARANTEE UI HAS DATA
    fast_results = results[:2]

    saved = 0
    vendors = []

    for r in fast_results:
        cleaned = clean_vendor_result(r)
        if not cleaned or not cleaned.get("phone"):
            continue

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

            vendors.append(
                {
                    "id": sr.id,
                    "vendor_name": sr.vendor_name,
                    "trade": sr.trade,
                    "phone": sr.phone,
                    "email": sr.email,
                    "source": sr.source,
                }
            )
        except Exception:
            continue

    await db.commit()

    # -------------------------
    # 5) Background fill (rest)
    # -------------------------
    background_tasks.add_task(
        background_discovery,
        project_request_id=project_request_id,
        trades=trades,
        address=data.address or "",
        db=db,
    )

    # -------------------------
    # 6) Activity log
    # -------------------------
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(project_request_id),
            action="contractor_search",
            payload={
                "trade": trades,
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
            "payload": {"trade": trades, "saved_results": saved},
        },
        db,
    )

    # -------------------------
    # 7) FINAL RESPONSE (NEVER EMPTY)
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "raw_results": len(results),
        "saved_results": saved,
        "vendors": vendors,
    }