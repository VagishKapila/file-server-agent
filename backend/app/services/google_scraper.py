import os
import requests
from typing import List, Dict

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

GOOGLE_PLACES_API_KEY = (
    os.environ.get("GOOGLE_PLACES_API_KEY")
    or os.environ.get("GOOGLE_MAPS_API_KEY")
)

def geocode_address(address: str):
    params = {"address": address, "key": GOOGLE_PLACES_API_KEY}
    res = requests.get(GEOCODE_URL, params=params).json()

    if res.get("status") != "OK":
        return None, None

    loc = res["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def google_search(trades: List[str], location: str, radius_meters: int) -> List[Dict]:
    lat, lng = geocode_address(location)
    if not lat:
        return []

    results = []

    for trade in trades:
        params = {
            "query": f"{trade} contractor",
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "key": GOOGLE_PLACES_API_KEY,
        }

        r = requests.get(TEXT_SEARCH_URL, params=params).json()
        if r.get("status") != "OK":
            continue

        for place in r.get("results", []):
            results.append({
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "trade": trade,
                "rating": place.get("rating"),
                "reviews": place.get("user_ratings_total"),
                "phone_e164": None,      # Google NOT trusted for phone
                "source": "google",
            })

    return results