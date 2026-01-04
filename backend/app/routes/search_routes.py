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
        raise HTTPException(status_code=400, detail="project_request_id is required")

    # -------------------------
    # 1) HARD CACHE RETURN (NO DISCOVERY)
    # ranked by intelligence first
    # -------------------------
    cached = await db.execute(
        text("""
            SELECT
                sr.id,
                sr.vendor_name,
                sr.trade,
                sr.phone,
                sr.email,
                sr.source,
                COALESCE(vs.success_score, 0) AS success_score,
                COALESCE(vs.accepted_jobs, 0) AS accepted_jobs
            FROM search_results sr
            LEFT JOIN vendor_scores vs
                ON vs.phone = sr.phone
            WHERE sr.project_request_id = :pid
            ORDER BY
                COALESCE(vs.success_score, 0) DESC,
                COALESCE(vs.accepted_jobs, 0) DESC,
                sr.id DESC
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
                    "success_score": r.success_score,
                    "accepted_jobs": r.accepted_jobs,
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
    # 3) DISCOVERY (ONLY ONCE)
    # HARD CAP = 5
    # -------------------------
    results = await search_subcontractors(
        trades=trades,
        radius="25",
        preferred=[],
        location=data.address or "",
        db=db,
    )

    results = results[:5]

    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned or not cleaned.get("phone"):
            continue

        phone = cleaned["phone"]

        try:
            # ---- save vendor result
            sr = SearchResult(
                project_request_id=project_request_id,
                vendor_name=cleaned["name"],
                trade=cleaned.get("trade") or trades[0],
                phone=phone,
                email=cleaned.get("email"),
                source=cleaned.get("source", "google"),
            )
            db.add(sr)
            await db.flush()
            saved += 1

            # ---- upsert intelligence score
            await db.execute(
                text("""
                    INSERT INTO vendor_scores (phone, seen_count)
                    VALUES (:phone, 1)
                    ON CONFLICT (phone)
                    DO UPDATE SET
                        seen_count = vendor_scores.seen_count + 1,
                        updated_at = now()
                """),
                {"phone": phone},
            )

        except Exception:
            continue

    await db.commit()

    # -------------------------
    # 4) FINAL RETURN (ranked)
    # -------------------------
    rows = await db.execute(
        text("""
            SELECT
                sr.id,
                sr.vendor_name,
                sr.trade,
                sr.phone,
                sr.email,
                sr.source,
                COALESCE(vs.success_score, 0) AS success_score,
                COALESCE(vs.accepted_jobs, 0) AS accepted_jobs
            FROM search_results sr
            LEFT JOIN vendor_scores vs
                ON vs.phone = sr.phone
            WHERE sr.project_request_id = :pid
            ORDER BY
                COALESCE(vs.success_score, 0) DESC,
                COALESCE(vs.accepted_jobs, 0) DESC,
                sr.id DESC
            LIMIT 50
        """),
        {"pid": project_request_id},
    )

    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "cached": False,
        "saved_results": saved,
        "vendors": [
            {
                "id": r.id,
                "vendor_name": r.vendor_name,
                "trade": r.trade,
                "phone": r.phone,
                "email": r.email,
                "source": r.source,
                "success_score": r.success_score,
                "accepted_jobs": r.accepted_jobs,
            }
            for r in rows.fetchall()
        ],
        "duration_ms": int((time.time() - t0) * 1000),
    }