from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from .google_scraper import google_search
from app.models.search_result import SearchResult

logger = logging.getLogger("match-engine")


# --------------------------------------------------
# UTILS
# --------------------------------------------------

def clean_bytes(obj: Any) -> Any:
    """Remove bytes so FastAPI never crashes when encoding JSON."""
    if isinstance(obj, bytes):
        return "<binary>"
    if isinstance(obj, dict):
        return {k: clean_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_bytes(i) for i in obj]
    return obj


def normalize_city(value: Optional[str]) -> str:
    """
    Frontend often sends full address like:
      '123 main street, San Jose'
    We only want the city token ('San Jose') for matching/sorting.
    """
    if not value:
        return ""
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    return (parts[-1] if parts else str(value)).strip().lower()


def normalize_trades(trades: Any) -> List[str]:
    """
    trades may arrive as:
      - [] / None
      - "Roofing"
      - ["Roofing", "HVAC"]
    """
    if not trades:
        return ["General Contractor"]
    if isinstance(trades, str):
        return [trades.strip()] if trades.strip() else ["General Contractor"]
    if isinstance(trades, list):
        cleaned = [str(t).strip() for t in trades if str(t).strip()]
        return cleaned if cleaned else ["General Contractor"]
    return ["General Contractor"]


def normalize_preferred(preferred: Any) -> set[str]:
    if not preferred:
        return set()
    if isinstance(preferred, str):
        return {preferred.strip().lower()} if preferred.strip() else set()
    if isinstance(preferred, list):
        return {str(p).strip().lower() for p in preferred if str(p).strip()}
    return set()


def _get_async_sessionmaker():
    """
    Your db.py naming has changed over time.
    This safely finds the async sessionmaker without hard-crashing imports.
    """
    import app.db as dbmod

    # Most common names we’ve seen in your codebases
    for name in (
        "async_session",          # (older) async_session = async_sessionmaker(...)
        "async_sessionmaker",     # sometimes exported directly
        "AsyncSessionLocal",      # common pattern
        "async_session_maker",
        "async_session_factory",
        "SessionLocal",
    ):
        if hasattr(dbmod, name):
            return getattr(dbmod, name)

    raise ImportError(
        "Could not find async sessionmaker in app.db. "
        "Expected one of: async_session, AsyncSessionLocal, SessionLocal, async_session_maker, etc."
    )


# --------------------------------------------------
# MAIN SEARCH ENGINE
# --------------------------------------------------

async def search_subcontractors(trades, radius, preferred, location):
    """
    Behavior (locked):
    - Always feels like a live Google search
    - DB-first learning to reduce API cost
    - Saves everything discovered
    - Returns callable vendors only (has phone, not do_not_call)
    - Sorts: same city first, preferred first
    """

    trades_list = normalize_trades(trades)
    preferred_set = normalize_preferred(preferred)
    job_city = normalize_city(location)

    # ---------------------------
    # Radius handling
    # ---------------------------
    try:
        miles = int(str(radius).split()[0])
    except Exception:
        miles = 50  # default
    radius_meters = miles * 1609

    SessionMaker = _get_async_sessionmaker()

    async with SessionMaker() as db:
        # ---------------------------
        # 1) DB-FIRST LOOKUP
        # ---------------------------
        db_q = (
            select(SearchResult)
            .where(SearchResult.trade.in_(trades_list))
        )
        db_res = await db.execute(db_q)
        cached: List[SearchResult] = db_res.scalars().all()

        callable_cached = [
            v for v in cached
            if getattr(v, "phone", None) and not getattr(v, "do_not_call", False)
        ]

        # If we already have enough callable vendors, skip Google
        use_cache_only = len(callable_cached) >= 6

        # ---------------------------
        # 2) GOOGLE SEARCH (if needed)
        # ---------------------------
        google_results: List[Dict[str, Any]] = []
        if not use_cache_only:
            # NOTE: google_search can be sync or async depending on your implementation.
            # Your current version looked sync, so keep it direct.
            google_results = google_search(trades_list, location, radius_meters) or []

            # Persist everything (even missing phone) for learning
            for g in google_results:
                try:
                    name = (g.get("name") or "").strip()
                    phone = g.get("phone")
                    city = normalize_city(g.get("city"))
                    trade_val = g.get("trade") or (trades_list[0] if trades_list else "General Contractor")

                    if not name:
                        continue

                    sr = SearchResult(
                        name=name,
                        trade=trade_val,
                        phone=phone,
                        city=city or None,
                        source="google",
                    )
                    db.add(sr)
                except Exception:
                    logger.exception("Failed saving SearchResult row")

            try:
                await db.commit()
            except Exception:
                logger.exception("DB commit failed for SearchResult saves")
                await db.rollback()

        # ---------------------------
        # 3) MERGE RESULTS (illusion preserved)
        #    - If google ran: show google results
        #    - else: show cached
        # ---------------------------
        source_pool: List[Any] = google_results if google_results else callable_cached

        merged: List[Dict[str, Any]] = []

        for v in source_pool:
            # dict from google OR ORM model from db
            if isinstance(v, dict):
                name = v.get("name") or ""
                phone = v.get("phone")
                city = normalize_city(v.get("city"))
            else:
                name = getattr(v, "name", "") or ""
                phone = getattr(v, "phone", None)
                city = normalize_city(getattr(v, "city", None))

            # Allow missing phone at discovery stage
            merged.append({
                "name": ...,
                "phone": phone,  # may be None
                "city": city,
                "preferred": ...,
                "same_city": ...,
            })

            name_norm = str(name).strip()
            if not name_norm:
                continue

            merged.append({
                "name": name_norm,
                "phone": phone,
                "city": city,
                "preferred": name_norm.lower() in preferred_set,
                "same_city": (city == job_city) if job_city else False,
                "source": "google" if google_results else "cache",
            })

        # ---------------------------
        # 4) SORT: SAME CITY FIRST, PREFERRED FIRST
        # ---------------------------
        merged.sort(key=lambda x: (not x["same_city"], not x["preferred"]))

        logger.info(
            "search_subcontractors | trades=%s miles=%s job_city=%s cache_only=%s returned=%d",
            trades_list, miles, job_city, use_cache_only, len(merged)
        )

        return clean_bytes(merged)