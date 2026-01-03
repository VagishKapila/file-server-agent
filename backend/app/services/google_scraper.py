import os
import requests
import phonenumbers
from typing import List, Dict, Optional

# -----------------------------
# ENV
# -----------------------------
GOOGLE_API_KEY = (
    os.getenv("GOOGLE_PLACES_API_KEY")
    or os.getenv("GOOGLE_MAPS_API_KEY")
)

if not GOOGLE_API_KEY:
    raise RuntimeError("❌ GOOGLE_PLACES_API_KEY / GOOGLE_MAPS_API_KEY not set")

# -----------------------------
# URLS
# -----------------------------
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"


# -----------------------------
# UTILS
# -----------------------------
def normalize_phone(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    try:
        p = phonenumbers.parse(raw, "US")
        if not phonenumbers.is_valid_number(p):
            return None
        return phonenumbers.format_number(
            p, phonenumbers.PhoneNumberFormat.E164
        )
    except Exception:
        return None


def geocode_address(address: str):
    r = requests.get(
        GEOCODE_URL,
        params={"address": address, "key": GOOGLE_API_KEY},
        timeout=10,
    ).json()

    if r.get("status") != "OK":
        return None, None

    loc = r["results"][0]["geometry"]["location"]
    return loc["lat"], loc["lng"]


def get_place_phone(place_id: str) -> Optional[str]:
    r = requests.get(
        DETAILS_URL,
        params={
            "place_id": place_id,
            "fields": "formatted_phone_number,international_phone_number",
            "key": GOOGLE_API_KEY,
        },
        timeout=10,
    ).json()

    result = r.get("result", {})
    raw = (
        result.get("international_phone_number")
        or result.get("formatted_phone_number")
    )

    return normalize_phone(raw)


# -----------------------------
# MAIN GOOGLE SEARCH
# -----------------------------
def google_search(
    trades: List[str],
    location: str,
    radius_meters: int = 40000,
) -> List[Dict]:
    """
    Google is PRIMARY discovery + phone source.
    Yelp is fallback elsewhere.
    """

    lat, lng = geocode_address(location)
    if not lat or not lng:
        return []

    results: List[Dict] = []
    seen = set()

    for trade in trades:
        params = {
            "query": f"{trade} contractor",
            "location": f"{lat},{lng}",
            "radius": radius_meters,
            "key": GOOGLE_API_KEY,
        }

        r = requests.get(
            TEXT_SEARCH_URL,
            params=params,
            timeout=15,
        ).json()

        if r.get("status") != "OK":
            continue

        for place in r.get("results", []):
            place_id = place.get("place_id")
            name = place.get("name")
            address = place.get("formatted_address")

            if not place_id or not name:
                continue

            phone = get_place_phone(place_id)

            dedupe_key = (name.lower(), phone or address)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            results.append(
                {
                    "name": name,
                    "address": address,
                    "trade": trade,
                    "phone": phone,            # 🔑 normalized E.164 or None
                    "phone_e164": phone,       # 🔑 for autodial compatibility
                    "rating": place.get("rating"),
                    "reviews": place.get("user_ratings_total"),
                    "source": "google",
                }
            )

    return results