import os
import requests
import phonenumbers

YELP_API_KEY = os.getenv("YELP_API_KEY")

def normalize_phone(raw_phone, default_country="US"):
    if not raw_phone:
        return None
    try:
        p = phonenumbers.parse(raw_phone, default_country)
        if not phonenumbers.is_valid_number(p):
            return None
        return phonenumbers.format_number(p, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        return None

def yelp_search(query: str, location: str):
    if not YELP_API_KEY:
        return []

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    url = "https://api.yelp.com/v3/businesses/search"

    params = {
        "term": f"{query} contractor",
        "location": location,
        "limit": 50,
    }

    r = requests.get(url, headers=headers, params=params).json()

    results = []
    for b in r.get("businesses", []):
        phone_e164 = normalize_phone(b.get("phone"))

        results.append({
            "name": b.get("name"),
            "address": " ".join(b.get("location", {}).get("display_address", [])),
            "phone_e164": phone_e164,
            "source": "yelp",
        })

    return results