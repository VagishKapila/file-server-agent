# app/services/google_places.py

import os
import requests
from typing import Dict, Optional
import time

GOOGLE_DETAILS_SLEEP = 0.12  # ~8 req/sec safe

GOOGLE_PLACES_API_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
)

if not GOOGLE_PLACES_API_KEY:
    raise RuntimeError("GOOGLE_PLACES_API_KEY not set")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def google_places_text_search(
    trade: str,
    location: str,
    radius_meters: int = 40000,
):
    """
    Google Places Text Search
    - Returns name + place_id
    - NO phone here by design
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
        results.append(
            {
                "name": p.get("name"),
                "formatted_address": p.get("formatted_address"),
                "place_id": p.get("place_id"),
                "rating": p.get("rating"),
                "reviews": p.get("user_ratings_total"),
                "source": "google",
            }
        )

    return results


def google_place_details(place_id: str) -> Optional[Dict]:
    """
    Google Place Details
    - Returns RAW Google keys (important)
    """
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,international_phone_number,website",
        "key": GOOGLE_PLACES_API_KEY,
    }

    time.sleep(GOOGLE_DETAILS_SLEEP)

    res = requests.get(DETAILS_URL, params=params, timeout=15).json()

    if res.get("status") != "OK":
        return None

    # IMPORTANT: keep Google’s original field names
    return res.get("result", {})