from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from .google_places import google_places_text_search, google_place_details
from app.services.yelp_enricher import enrich_with_yelp
from app.models.search_result import SearchResult


def normalize_city(city: str | None) -> str:
    return (city or "").strip().lower()


def normalize_name(name: str) -> str:
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
    FINAL SOURCE OF TRUTH:
    - Google Places = primary
    - Place Details = phone
    - Yelp = fallback
    - DB = memory
    """

    preferred_set = {p.lower() for p in preferred}
    job_city = normalize_city(location)

    # ---------------------------
    # 1) Load cached vendors
    # ---------------------------
    db_results = await db.execute(
        select(SearchResult).where(SearchResult.trade.in_(trades))
    )
    cached = db_results.scalars().all()

    merged = []
    seen = set()

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

    # ---------------------------
    # 2) Google Places discovery
    # ---------------------------
    for trade in trades:
        places = google_places_text_search(trade, location)

        for p in places:
            place_id = p.get("place_id")
            name = p.get("name")

            if not place_id or not name:
                continue

            details = google_place_details(place_id)

            phone = (
                details.get("international_phone_number")
                or details.get("formatted_phone_number")
            )

            source = "google_places"

            # ---------------------------
            # 3) Yelp fallback
            # ---------------------------
            if not phone:
                enriched = enrich_with_yelp(name=name, location=location)
                phone = enriched.get("phone")
                if phone:
                    source = enriched.get("source", "yelp")

            city = normalize_city(
                p.get("formatted_address")
            )

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

    # ---------------------------
    # 4) Sort
    # ---------------------------
    merged.sort(
        key=lambda x: (
            not x["callable"],
            not x["same_city"],
            not x["preferred"],
        )
    )

    return merged