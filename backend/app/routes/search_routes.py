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


@router.post("/search")
async def perform_search(
    data: SearchRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(400, "project_request_id required")

    # -----------------------------------
    # 1) FAST DB RETURN (NO GOOGLE)
    # -----------------------------------
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
            "cached": True,
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

    # -----------------------------------
    # 2) NORMALIZE TRADES
    # -----------------------------------
    trades = []
    if data.category:
        trades.append(data.category.strip())
    trades.extend([t.strip() for t in data.tags if t.strip()])
    if not trades:
        trades = ["General Contractor"]

    # -----------------------------------
    # 3) BACKGROUND GOOGLE SEARCH
    # -----------------------------------
    background.add_task(
        run_background_search,
        project_request_id,
        trades,
        data.address or "",
    )

    # -----------------------------------
    # 4) IMMEDIATE RESPONSE (FAST)
    # -----------------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "cached": False,
        "vendors": [],
        "message": "Search running in background",
        "duration_ms": int((time.time() - t0) * 1000),
    }


# ==================================================
# BACKGROUND TASK (SLOW STUFF GOES HERE)
# ==================================================
async def run_background_search(
    project_request_id: int,
    trades: list[str],
    address: str,
):
    from app.db import async_session

    async with async_session() as db:
        results = await search_subcontractors(
            trades=trades,
            radius="25",
            preferred=[],
            location=address,
            db=db,
        )

        results = results[:10]  # HARD CAP

        for r in results:
            cleaned = clean_vendor_result(r)
            if not cleaned or not cleaned.get("phone"):
                continue

            sr = SearchResult(
                project_request_id=project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned.get("trade") or trades[0],
                phone=cleaned.get("phone"),
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
            db.add(sr)

        await db.commit()