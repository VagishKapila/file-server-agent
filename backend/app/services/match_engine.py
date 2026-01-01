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


def normalize_trades(trades):
    """
    Frontend may send:
    - []
    - ["Roofing"]
    - "Roofing"
    - None
    """
    if not trades:
        return ["General Contractor"]

    if isinstance(trades, str):
        return [trades]

    if isinstance(trades, list) and len(trades) > 0:
        return trades

    return ["General Contractor"]


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
    # 🔒 INPUT NORMALIZATION (CRITICAL)
    # ---------------------------
    trades = normalize_trades(trades)
    preferred = preferred or []

    if not location or not location.strip():
        location = "San Jose, CA"

    job_city = normalize_city(location)
    preferred_set = {p.lower() for p in preferred}

    # ---------------------------
    # Radius handling
    # ---------------------------
    try:
        miles = int(str(radius).split()[0])
    except Exception:
        miles = 50  # default

    radius_meters = miles * 1609

    merged = []

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

        callable_cached = [
            v for v in cached
            if v.phone and not v.do_not_call
        ]

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

            await db.commit()

        # ---------------------------
        # 3️⃣ MERGE RESULTS (illusion preserved)
        # ---------------------------
        source_pool = google_results if google_results else cached

        for v in source_pool:
            is_dict = isinstance(v, dict)

            phone = v.get("phone") if is_dict else v.phone
            if not phone:
                continue

            city = normalize_city(v.get("city") if is_dict else v.city)
            name = v.get("name") if is_dict else v.name

            merged.append({
                "name": name,
                "phone": phone,
                "city": city,
                "preferred": name.lower() in preferred_set,
                "same_city": city == job_city,
            })

    # ---------------------------
    # 4️⃣ SORT: SAME CITY + PREFERRED FIRST
    # ---------------------------
    merged.sort(
        key=lambda x: (
            not x["same_city"],
            not x["preferred"],
        )
    )

    return clean_bytes(merged)