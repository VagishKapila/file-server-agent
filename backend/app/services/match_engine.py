from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .google_scraper import google_search
from app.models.search_result import SearchResult


# --------------------------------------------------
# UTILS
# --------------------------------------------------

def clean_bytes(obj):
    if isinstance(obj, bytes):
        return "<binary>"
    if isinstance(obj, dict):
        return {k: clean_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_bytes(i) for i in obj]
    return obj


def normalize_city(city: str | None) -> str:
    return (city or "").strip().lower()


# --------------------------------------------------
# MAIN SEARCH ENGINE
# --------------------------------------------------

async def search_subcontractors(
    trades: List[str],
    radius,
    preferred,
    location,
    db: AsyncSession,
):
    """
    Behavior (RESTORED, SAFE):
    - DB is READ-ONLY memory
    - Google is discovery only
    - ALL persistence handled by routes/search_routes.py
    """

    # ---------------------------
    # Radius handling
    # ---------------------------
    try:
        miles = int(str(radius).split()[0])
    except Exception:
        miles = 50

    radius_meters = miles * 1609
    preferred_set = {p.lower() for p in preferred}
    job_city = normalize_city(location)

    # ---------------------------
    # 1️⃣ DB-FIRST LOOKUP (READ ONLY)
    # ---------------------------
    db_results = await db.execute(
        select(SearchResult).where(SearchResult.trade.in_(trades))
    )
    cached = db_results.scalars().all()

    callable_cached = [v for v in cached if v.phone]
    use_cache_only = len(callable_cached) >= 6

    google_results = []

    # ---------------------------
    # 2️⃣ GOOGLE SEARCH (NO DB WRITE)
    # ---------------------------
    if not use_cache_only:
        google_results = google_search(trades, location, radius_meters)

    # ---------------------------
    # 3️⃣ MERGE RESULTS
    # ---------------------------
    merged = []
    seen = set()

    # normalize cached DB rows
    for v in cached:
        name = v.vendor_name
        phone = v.phone
        city = ""
        source = v.source or "db"

        if not name:
            continue

        key = (name.lower(), city)
        if key in seen:
            continue
        seen.add(key)

        merged.append({
            "name": name,
            "phone": phone,
            "city": city,
            "callable": bool(phone),
            "preferred": name.lower() in preferred_set,
            "same_city": False,
            "source": source,
        })

    # normalize google dict results
    for g in google_results:
        name = (g.get("name") or "").strip()
        if not name:
            continue

        city = normalize_city(g.get("city") or g.get("address"))
        phone = g.get("phone") or g.get("phone_e164")

        key = (name.lower(), city)
        if key in seen:
            continue
        seen.add(key)

        merged.append({
            "name": name,
            "phone": phone,
            "city": city,
            "callable": bool(phone),
            "preferred": name.lower() in preferred_set,
            "same_city": city == job_city if city else False,
            "source": "google",
        })

    # ---------------------------
    # 4️⃣ SORT PRIORITY
    # ---------------------------
    merged.sort(
        key=lambda x: (
            not x["same_city"],
            not x["preferred"],
            not x["callable"],
        )
    )

    return clean_bytes(merged)