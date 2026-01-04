# EOF: backend/app/routes/search.py

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
# Background worker
# =========================
async def run_background_search(
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

    results = results[:10]  # HARD CAP (speed + sanity)

    saved = 0
    for r in results:
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
        except Exception:
            continue

    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(project_request_id),
            action="contractor_search_background",
            payload={
                "trade": trades,
                "saved_results": saved,
            },
        )
    )

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

    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(status_code=400, detail="project_request_id is required")

    # -------------------------
    # 1) FAST CACHE RETURN (<50ms)
    # -------------------------
    rows = await db.execute(
        text("""
            SELECT id, vendor_name, trade, phone, email, source
            FROM search_results
            WHERE project_request_id = :pid
            ORDER BY id DESC
            LIMIT 50
        """),
        {"pid": project_request_id},
    )

    cached = rows.fetchall()
    if cached:
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
                for r in cached
            ],
            "duration_ms": int((time.time() - t0) * 1000),
        }

    # -------------------------
    # 2) Normalize trades
    # -------------------------
    trades = []
    if data.category:
        trades.append(data.category.strip())
    trades.extend([t.strip() for t in data.tags if t.strip()])
    if not trades:
        trades = ["General Contractor"]

    # -------------------------
    # 3) Fire background search
    # -------------------------
    background_tasks.add_task(
        run_background_search,
        project_request_id=project_request_id,
        trades=trades,
        address=data.address or "",
        db=db,
    )

    # -------------------------
    # 4) INSTANT RESPONSE
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": [],
        "message": "Search started",
        "duration_ms": int((time.time() - t0) * 1000),
    }