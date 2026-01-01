from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .google_scraper import google_search
from app.models.search_result import SearchResult


# --------------------------------------------------
# UTILS
# --------------------------------------------------

def clean_bytes(obj):
    """Remove bytes so FastAPI never crashes when encoding JSON."""
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
    db: AsyncSession,   # ✅ injected session
):
    """
    Behavior:
    - Google results are ALWAYS collected & saved (phone or not)
    - DB is the long-term memory
    - Callable vendors are preferred, not required
    - Yelp enrichment can happen later
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
    # 1️⃣ DB-FIRST LOOKUP
    # ---------------------------
    db_results = await db.execute(
        select(SearchResult).where(SearchResult.trade.in_(trades))
    )

    cached = db_results.scalars().all()

    callable_cached = [
        v for v in cached
        if v.phone and not v.do_not_call
    ]

    use_cache_only = len(callable_cached) >= 6
    google_results = []

    # ---------------------------
    # 2️⃣ GOOGLE SEARCH (ALWAYS SAVE)
    # ---------------------------
    if not use_cache_only:
        google_results = google_search(trades, location, radius_meters)

        for g in google_results:
            name = (g.get("name") or "").strip()
            city = normalize_city(g.get("city") or g.get("address"))

            if not name:
                continue

            db.add(
                SearchResult(
                    name=name,
                    trade=g.get("trade"),
                    phone=None,           # Yelp later
                    city=city,
                    source="google",
                )
            )

        await db.commit()

    # ---------------------------
    # 3️⃣ MERGE RESULTS
    # ---------------------------
    merged = []
    source_pool = cached + google_results
    seen = set()

    for v in source_pool:
        if isinstance(v, dict):
            name = v.get("name")
            phone = v.get("phone") or v.get("phone_e164")
            city = normalize_city(v.get("city") or v.get("address"))
            source = "google"
        else:
            name = v.name
            phone = v.phone
            city = normalize_city(v.city)
            source = v.source

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
            "same_city": city == job_city,
            "source": source,
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