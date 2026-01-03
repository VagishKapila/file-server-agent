import os
import requests
import phonenumbers

YELP_API_KEY = os.getenv("YELP_API_KEY")


def normalize_phone(raw):
    try:
        p = phonenumbers.parse(raw, "US")
        if not phonenumbers.is_valid_number(p):
            return None
        return phonenumbers.format_number(
            p, phonenumbers.PhoneNumberFormat.E164
        )
    except Exception:
        return None


def enrich_with_yelp(name: str, location: str) -> dict:
    if not YELP_API_KEY:
        return {}

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    params = {
        "term": name,
        "location": location,
        "limit": 3,
    }

    r = requests.get(
        "https://api.yelp.com/v3/businesses/search",
        headers=headers,
        params=params,
    ).json()

    for b in r.get("businesses", []):
        phone = normalize_phone(b.get("phone"))
        if phone:
            return {
                "phone": phone,
                "source": "yelp",
            }

    return {}