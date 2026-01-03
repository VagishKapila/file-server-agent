from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.services.google_places import (
    google_places_text_search,
    google_place_details,
)
from app.services.yelp_enricher import enrich_with_yelp
from app.models.search_result import SearchResult


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


async def search_subcontractors(
    trades: List[str],
    radius,
    preferred,
    location,
    db: AsyncSession,
):
    """
    SOURCE ORDER (FINAL):
    1. DB cache
    2. Google Places Text Search
    3. Google Place Details (phone)
    4. Yelp fallback (phone only)
    """

    preferred_set = {p.lower() for p in preferred}
    job_city = normalize_city(location)

    merged = []
    seen = set()

    # -------------------------------------------------
    # 1) LOAD CACHED VENDORS (DB MEMORY)
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
    # 2) GOOGLE PLACES DISCOVERY
    # -------------------------------------------------
    for trade in trades:
        places = google_places_text_search(trade, location)

        for p in places:
            name = p.get("name")
            place_id = p.get("place_id")

            if not name:
                continue

            phone = None
            source = "google_places"

            # -------------------------------------------------
            # 2A) GOOGLE PLACE DETAILS (PHONE)
            # -------------------------------------------------
            if place_id:
                details = google_place_details(place_id)
                if details:
                    phone = details.get("phone")

            # -------------------------------------------------
            # 2B) YELP FALLBACK (ONLY IF PHONE MISSING)
            # -------------------------------------------------
            if not phone:
                enriched = enrich_with_yelp(
                    name=name,
                    location=location,
                )
                if enriched and enriched.get("phone"):
                    phone = enriched["phone"]
                    source = enriched.get("source", "yelp")

            city = normalize_city(p.get("address") or "")

            key = (normalize_name(name), phone or city)
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
                "source": source,
            })

    # -------------------------------------------------
    # 3) SORT (CALLABLE → SAME CITY → PREFERRED)
    # -------------------------------------------------
    merged.sort(
        key=lambda x: (
            not x["callable"],
            not x["same_city"],
            not x["preferred"],
        )
    )

    return merged