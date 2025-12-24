import os
import requests

YELP_API_KEY = os.getenv("YELP_API_KEY")

def yelp_search(query, location):
    if not YELP_API_KEY:
        return []

    headers = {"Authorization": f"Bearer {YELP_API_KEY}"}
    url = "https://api.yelp.com/v3/businesses/search"

    params = {
        "term": f"{query} contractor",
        "location": location,
        "limit": 10
    }

    r = requests.get(url, headers=headers, params=params).json()

    results = []
    for b in r.get("businesses", []):
        results.append({
            "name": b.get("name"),
            "rating": b.get("rating"),
            "address": " ".join(b.get("location", {}).get("display_address", [])),
            "source": "yelp"
        })

    return results