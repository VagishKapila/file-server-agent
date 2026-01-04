# EOF: backend/app/routes/search.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time

from app.db import get_db
from app.models.search_result import SearchResult
from app.services.match_engine import search_subcontractors
from app.utils.vendor_guard import clean_vendor_result

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
# Search endpoint (FAST + SAFE)
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
        raise HTTPException(status_code=400, detail="project_request_id is required")

    # -------------------------
    # 1) FAST PATH — DB CACHE (<50ms)
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
            "duration_ms": int((time.time() - t0) * 1000),
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
    # 3) RUN DISCOVERY (SYNC — UI NEEDS RESULTS)
    # HARD CAP = 5 (speed)
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    results = results[:5]  # 🔥 SPEED FIX

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

    await db.commit()

    # -------------------------
    # 4) RETURN FOR UI
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

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": vendors,
        "saved_results": saved,
        "duration_ms": int((time.time() - t0) * 1000),
    }