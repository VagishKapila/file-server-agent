import asyncio
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_result import SearchResult
from app.services.google_places import (
    google_places_text_search,
    google_place_details,
)
from app.services.yelp_enricher import enrich_with_yelp


# -------------------------
# Normalizers
# -------------------------
def normalize_city(city: str | None) -> str:
    return (city or "").strip().lower()


def normalize_name(name: str | None) -> str:
    return (
        (name or "")
        .lower()
        .replace(",", "")
        .replace(".", "")
        .replace("&", "and")
        .strip()
    )


# -------------------------
# Safe wrappers (threaded)
# -------------------------
async def _google_search_safe(trade: str, location: str):
    try:
        return await asyncio.to_thread(
            google_places_text_search,
            trade,
            location,
        )
    except Exception:
        return []


async def _google_details_safe(place_id: str):
    try:
        return await asyncio.to_thread(
            google_place_details,
            place_id,
        )
    except Exception:
        return None


async def _yelp_safe(name: str, location: str):
    try:
        return await asyncio.to_thread(
            enrich_with_yelp,
            name=name,
            location=location,
        )
    except Exception:
        return None


# -------------------------
# MAIN ENTRY
# -------------------------
async def search_subcontractors(
    trades: List[str],
    radius,
    preferred,
    location,
    db: AsyncSession,
):
    """
    FINAL PIPELINE (SAFE + FAST)

    1. DB cache
    2. Google text search (parallel per trade)
    3. Google details + Yelp fallback (parallel per place)
    4. Sort callable → same city → preferred
    """

    preferred_set = {p.lower() for p in preferred}
    job_city = normalize_city(location)

    merged = []
    seen = set()

    # -------------------------------------------------
    # 1) DB CACHE (FAST, NON-BLOCKING)
    # -------------------------------------------------
    db_results = await db.execute(
        select(SearchResult).where(SearchResult.trade.in_(trades))
    )
    cached = db_results.scalars().all()

    for v in cached:
        if not v.vendor_name:
            continue

        key = (normalize_name(v.vendor_name), v.phone or "")
        if key in seen:
            continue
        seen.add(key)

        merged.append({
            "name": v.vendor_name,
            "phone": v.phone,
            "city": "",
            "callable": bool(v.phone),
            "preferred": v.vendor_name.lower() in preferred_set,
            "same_city": False,
            "source": v.source or "db",
        })

    # -------------------------------------------------
    # 2) GOOGLE SEARCH (PARALLEL PER TRADE)
    # -------------------------------------------------
    google_tasks = [
        _google_search_safe(trade, location)
        for trade in trades
    ]

    google_batches = await asyncio.gather(*google_tasks)

    # HARD CAP to avoid explosion
    places = []
    for batch in google_batches:
        places.extend(batch[:5])  # max 5 per trade

    # -------------------------------------------------
    # 3) DETAILS + YELP (PARALLEL PER PLACE)
    # -------------------------------------------------
    async def enrich_place(p):
        name = p.get("name")
        place_id = p.get("place_id")

        if not name:
            return None

        phone = None
        source = "google_places"

        if place_id:
            details = await _google_details_safe(place_id)
            if details:
                phone = details.get("phone")

        if not phone:
            enriched = await _yelp_safe(name, location)
            if enriched and enriched.get("phone"):
                phone = enriched["phone"]
                source = enriched.get("source", "yelp")

        city = normalize_city(p.get("address") or "")

        return {
            "name": name,
            "phone": phone,
            "city": city,
            "callable": bool(phone),
            "preferred": name.lower() in preferred_set,
            "same_city": city == job_city if city else False,
            "source": source,
        }

    enrichment_tasks = [
        enrich_place(p)
        for p in places
    ]

    enriched_results = await asyncio.gather(*enrichment_tasks)

    for e in enriched_results:
        if not e:
            continue

        key = (normalize_name(e["name"]), e["phone"] or e["city"])
        if key in seen:
            continue
        seen.add(key)
        merged.append(e)

    # -------------------------------------------------
    # 4) SORT (UNCHANGED BEHAVIOR)
    # -------------------------------------------------
    merged.sort(
        key=lambda x: (
            not x["callable"],
            not x["same_city"],
            not x["preferred"],
        )
    )

    return merged