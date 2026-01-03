import os
import requests

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"


def google_places_text_search(query: str, location: str):
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    params = {
        "query": f"{query} contractor in {location}",
        "key": GOOGLE_API_KEY,
    }

    resp = requests.get(TEXT_SEARCH_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return data.get("results", [])


def google_place_details(place_id: str):
    if not GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY not set")

    params = {
        "place_id": place_id,
        "fields": "name,formatted_phone_number,international_phone_number,website",
        "key": GOOGLE_API_KEY,
    }

    resp = requests.get(DETAILS_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    return data.get("result", {})
