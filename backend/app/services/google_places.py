import os
import requests

GOOGLE_API_KEY = (
    os.getenv("GOOGLE_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
    or os.getenv("GOOGLE_PLACES_API_KEY")
)

if not GOOGLE_API_KEY:
    raise RuntimeError("GOOGLE_API_KEY not set")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def google_places_text_search(trade: str, location: str):
    params = {
        "query": f"{trade} contractor",
        "location": location,
        "key": GOOGLE_API_KEY,
    }

    r = requests.get(TEXT_SEARCH_URL, params=params, timeout=10)
    r.raise_for_status()

    data = r.json()
    if data.get("status") != "OK":
        return []

    results = []

    for place in data.get("results", []):
        results.append({
            "place_id": place.get("place_id"),
            "name": place.get("name"),
            "address": place.get("formatted_address"),
            "trade": trade,
            "source": "google",
        })

    return results


def google_place_details(place_id: str):
    if not place_id:
        return {}

    r = requests.get(
        DETAILS_URL,
        params={
            "place_id": place_id,
            "fields": "formatted_phone_number,website",
            "key": GOOGLE_API_KEY,
        },
        timeout=10,
    )

    if r.status_code != 200:
        return {}

    data = r.json().get("result", {})
    return {
        "phone": data.get("formatted_phone_number"),
        "website": data.get("website"),
    }