# EOF: backend/app/routes/search_routes.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time

from app.db import get_db

router = APIRouter()


class SearchRequest(BaseModel):
    project_request_id: int | None = None
    project_id: int | None = None
    category: str | None = None
    tags: list[str] = []
    address: str | None = None


def extract_city(address: str | None) -> str:
    if not address:
        return ""
    return address.split(",")[0].strip().lower()


@router.post("/search")
async def perform_search(
    data: SearchRequest,
    db: AsyncSession = Depends(get_db),
):
    t0 = time.time()

    project_request_id = data.project_request_id or data.project_id
    if not project_request_id:
        raise HTTPException(status_code=400, detail="project_request_id required")

    city = extract_city(data.address)

    # -------------------------
    # 1) SMART DB CACHE (wins)
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
                COALESCE(vs.score, 0) AS score
            FROM search_results sr
            LEFT JOIN vendor_scores vs
              ON vs.vendor_phone = sr.phone
             AND vs.trade = sr.trade
             AND vs.city = :city
            WHERE sr.project_request_id = :pid
            ORDER BY score DESC, sr.id DESC
            LIMIT 5
        """),
        {
            "pid": project_request_id,
            "city": city,
        },
    )

    results = rows.fetchall()
    if results:
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
                    "score": float(r.score),
                }
                for r in results
            ],
            "duration_ms": int((time.time() - t0) * 1000),
        }

    # -------------------------
    # 2) EMPTY = UI SAFE
    # (background discovery fills DB)
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "vendors": [],
        "message": "No cached vendors yet",
        "duration_ms": int((time.time() - t0) * 1000),
    }