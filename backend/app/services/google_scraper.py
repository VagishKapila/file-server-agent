import os
import requests
from typing import List, Dict
PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

GOOGLE_PLACES_API_KEY = (
    os.environ.get("GOOGLE_PLACES_API_KEY")
    or os.environ.get("GOOGLE_MAPS_API_KEY")
)

TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


def geocode_address(address: str):
    """Convert address string → (lat, lng)"""
    params = {"address": address, "key": GOOGLE_PLACES_API_KEY}
    res = requests.get(GEOCODE_URL, params=params).json()

    if res.get("status") != "OK":
        print("❌ Geocoding failed:", res)
        return None, None

    loc = res["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]

def get_place_phone(place_id: str):
    """Fetch phone number for a Google Place ID"""
    if not place_id:
        return None

    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number",
        "key": GOOGLE_PLACES_API_KEY,
    }

    res = requests.get(PLACE_DETAILS_URL, params=params).json()

    if res.get("status") != "OK":
        return None

    return res.get("result", {}).get("formatted_phone_number")

def google_search(trades: List[str], location: str, radius_meters: int) -> List[Dict]:
    """Perform Google Places Text Search for subcontractors."""

    lat, lng = geocode_address(location)
    if not lat:
        print("❌ No coordinates returned")
        return []

    final_results = []

    for trade in trades:
        query = f"{trade} contractor"

        params = {
            "query": query,
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "key": GOOGLE_PLACES_API_KEY,
        }

        print("🔍 Calling Google Places with:", params)

        response = requests.get(TEXT_SEARCH_URL, params=params).json()

        print("📡 Google response status:", response.get("status"))

        if response.get("status") not in ["OK", "ZERO_RESULTS"]:
            print("❌ Google returned error:", response)
            continue

        for place in response.get("results", []):
            phone = get_place_phone(place.get("place_id"))

            final_results.append({
                "name": place.get("name"),
                "address": place.get("formatted_address"),
                "rating": place.get("rating"),
                "total_reviews": place.get("user_ratings_total"),
                "trade": trade,
                "phone": phone,  # 🔥 THIS IS THE FIX
                "source": "google",
            })

    print(f"✅ Returning {len(final_results)} results")
    return final_results