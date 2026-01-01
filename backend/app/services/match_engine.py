from .google_scraper import google_search
from sqlalchemy import select
from app.db import async_session
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

async def search_subcontractors(trades, radius, preferred, location):
    """
    Behavior:
    - Always feels like a live Google search
    - Uses DB-first learning to reduce API cost
    - Saves everything
    - Returns callable vendors only
    """

    # ---------------------------
    # Radius handling
    # ---------------------------
    try:
        miles = int(str(radius).split()[0])
    except Exception:
        miles = 50  # sensible default

    radius_meters = miles * 1609

    preferred_set = {p.lower() for p in preferred}
    job_city = normalize_city(location)

    results = []

    async with async_session() as db:

        # ---------------------------
        # 1️⃣ DB-FIRST LOOKUP
        # ---------------------------
        db_results = await db.execute(
            select(SearchResult)
            .where(SearchResult.trade.in_(trades))
            .where(SearchResult.city.isnot(None))
        )

        cached = db_results.scalars().all()

        # callable vendors in DB
        callable_cached = [
            v for v in cached
            if v.phone and not v.do_not_call
        ]

        # If we already have enough vendors, skip Google
        use_cache_only = len(callable_cached) >= 6

        # ---------------------------
        # 2️⃣ GOOGLE SEARCH (if needed)
        # ---------------------------
        google_results = []

        if not use_cache_only:
            google_results = google_search(trades, location, radius_meters)

            for g in google_results:
                name = (g.get("name") or "").strip()
                phone = g.get("phone")
                city = normalize_city(g.get("city"))

                sr = SearchResult(
                    name=name,
                    trade=g.get("trade"),
                    phone=phone,
                    city=city,
                    source="google",
                )

                db.add(sr)
                results.append(g)

            await db.commit()

        # ---------------------------
        # 3️⃣ MERGE RESULTS (illusion preserved)
        # ---------------------------
        merged = []

        source_pool = google_results if google_results else cached

        for v in source_pool:
            phone = v.get("phone") if isinstance(v, dict) else v.phone
            city = normalize_city(v.get("city") if isinstance(v, dict) else v.city)

            if not phone:
                continue

            merged.append({
                "name": v.get("name") if isinstance(v, dict) else v.name,
                "phone": phone,
                "city": city,
                "preferred": (v.get("name") or "").lower() in preferred_set,
                "same_city": city == job_city,
            })

    # ---------------------------
    # 4️⃣ SORT: SAME CITY FIRST
    # ---------------------------
    merged.sort(
        key=lambda x: (
            not x["same_city"],
            not x["preferred"]
        )
    )

    return clean_bytes(merged)