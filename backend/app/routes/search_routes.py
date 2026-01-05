import asyncio
import time
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

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
# Helpers
# =========================
def _norm(val: str | None) -> str:
    return (val or "").strip().lower()


def _make_cache_key(trades: list[str], address: str | None) -> str:
    raw = "|".join(sorted(_norm(t) for t in trades)) + "||" + _norm(address)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def _fetch_global_results(
    db: AsyncSession,
    trades: list[str],
    limit: int = 50,
):
    rows = await db.execute(
        text("""
            SELECT id, vendor_name, trade, phone, email, source
            FROM search_results
            WHERE trade = ANY(:trades)
            ORDER BY id DESC
            LIMIT :limit
        """),
        {"trades": trades, "limit": limit},
    )
    return rows.fetchall()


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
    # 1) Ensure project exists
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

    cache_key = _make_cache_key(trades, data.address)

    # -------------------------
    # 2.5) CACHE HIT (GLOBAL)
    # -------------------------
    try:
        since = datetime.utcnow() - timedelta(minutes=15)
        cached = await db.execute(
            text("""
                SELECT id
                FROM activity_log
                WHERE action = 'contractor_search'
                  AND (payload->>'cache_key') = :key
                  AND created_at >= :since
                LIMIT 1
            """),
            {"key": cache_key, "since": since},
        )

        if cached.first():
            rows = await _fetch_global_results(db, trades)
            vendors = [
                {
                    "id": r.id,
                    "vendor_name": r.vendor_name,
                    "trade": r.trade,
                    "phone": r.phone,
                    "email": r.email,
                    "source": r.source,
                }
                for r in rows
            ]

            print(
                "CACHE HIT (GLOBAL) | vendors=",
                len(vendors),
                "ms=",
                int((time.time() - t0) * 1000),
            )

            return {
                "status": "ok",
                "project_request_id": project_request_id,
                "raw_results": 0,
                "saved_results": 0,
                "cached": True,
                "vendors": vendors,
            }

    except Exception as e:
        print("CACHE CHECK FAILED:", e)

    # -------------------------
    # 3) DISCOVERY (HARD TIMEOUT)
    # -------------------------
    t_discovery = time.time()
    try:
        results = await asyncio.wait_for(
            search_subcontractors(
                trades=trades,
                radius="25",
                preferred=[],
                location=data.address or "",
                db=db,
            ),
            timeout=20,
        )
    except asyncio.TimeoutError:
        print("DISCOVERY TIMEOUT | pid=", project_request_id)
        results = []
    except Exception as e:
        print("DISCOVERY ERROR:", e)
        results = []

    print(
        "DISCOVERY DONE | raw=",
        len(results),
        "ms=",
        int((time.time() - t_discovery) * 1000),
    )

    # -------------------------
    # 4) PERSIST RESULTS
    # -------------------------
    saved = 0

    for r in results:
        cleaned = clean_vendor_result(r)
        if not cleaned:
            continue

        cleaned.pop("callable", None)
        cleaned.pop("confidence", None)
        cleaned.pop("score", None)

        name = cleaned["name"]
        trade = cleaned.get("trade") or trades[0]
        phone = cleaned.get("phone")
        email = cleaned.get("email")
        source = cleaned.get("source", "google")

        try:
            if phone:
                existing = await db.execute(
                    text("""
                        SELECT id, phone
                        FROM search_results
                        WHERE vendor_name = :name
                          AND trade = :trade
                          AND source = :source
                        ORDER BY id DESC
                        LIMIT 1
                    """),
                    {
                        "name": name,
                        "trade": trade,
                        "source": source,
                    },
                )
                row = existing.first()
                if row and not row.phone:
                    await db.execute(
                        text("""
                            UPDATE search_results
                            SET phone = :phone,
                                email = COALESCE(email, :email)
                            WHERE id = :id
                        """),
                        {"phone": phone, "email": email, "id": row.id},
                    )
                    saved += 1
                    continue

            sr = SearchResult(
                project_request_id=project_request_id,
                vendor_name=name,
                trade=trade,
                phone=phone,
                email=email,
                source=source,
            )
            db.add(sr)
            await db.flush()
            saved += 1

        except Exception as e:
            print("❌ SearchResult insert failed:", e)

    # -------------------------
    # 5) FINAL GLOBAL FETCH
    # -------------------------
    rows = await _fetch_global_results(db, trades)

    vendors = [
        {
            "id": r.id,
            "vendor_name": r.vendor_name,
            "trade": r.trade,
            "phone": r.phone,
            "email": r.email,
            "source": r.source,
        }
        for r in rows
    ]

    # -------------------------
    # 6) ACTIVITY LOG
    # -------------------------
    db.add(
        ActivityLog(
            user_id="demo-user",
            project_id=str(project_request_id),
            action="contractor_search",
            payload={
                "trade": trades,
                "address": data.address,
                "raw_results": len(results),
                "saved_results": saved,
                "cache_key": cache_key,
            },
        )
    )

    await db.commit()

    # -------------------------
    # 7) ASYNC ACTIVITY FEED
    # -------------------------
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

    print(
        "SEARCH COMPLETE | saved=",
        saved,
        "total_ms=",
        int((time.time() - t0) * 1000),
    )

    # -------------------------
    # 8) FINAL RESPONSE
    # -------------------------
    return {
        "status": "ok",
        "project_request_id": project_request_id,
        "raw_results": len(results),
        "saved_results": saved,
        "vendors": vendors,
    }