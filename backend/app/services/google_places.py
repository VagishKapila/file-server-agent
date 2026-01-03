# app/services/google_places.py

import os
import requests
from typing import Dict, Optional

GOOGLE_PLACES_API_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
)

if not GOOGLE_PLACES_API_KEY:
    raise RuntimeError("GOOGLE_PLACES_API_KEY not set")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def google_places_text_search(trade: str, location: str, radius_meters: int = 40000):
    """
    Returns raw places with place_id (NO phone here)
    """
    query = f"{trade} contractor"

    params = {
        "query": query,
        "location": location,
        "radius": radius_meters,
        "key": GOOGLE_PLACES_API_KEY,
    }

    res = requests.get(TEXT_SEARCH_URL, params=params, timeout=15).json()

    if res.get("status") != "OK":
        return []

    results = []

    for p in res.get("results", []):
        results.append({
            "name": p.get("name"),
            "address": p.get("formatted_address"),
            "place_id": p.get("place_id"),
            "rating": p.get("rating"),
            "reviews": p.get("user_ratings_total"),
            "source": "google",
        })

    return results


def google_place_details(place_id: str) -> Optional[Dict]:
    """
    Fetch phone + website from Place Details
    """
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,international_phone_number,website",
        "key": GOOGLE_PLACES_API_KEY,
    }

    res = requests.get(DETAILS_URL, params=params, timeout=15).json()

    if res.get("status") != "OK":
        return None

    result = res.get("result", {})

    return {
        "phone": (
            result.get("international_phone_number")
            or result.get("formatted_phone_number")
        ),
        "website": result.get("website"),
    }