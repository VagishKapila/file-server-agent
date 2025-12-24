from google_search import google_search
from yelp_search import yelp_search

def merge_google_yelp(trades, location, radius_meters=30000):
    google_results = google_search(trades, location, radius_meters)
    yelp_results = yelp_search("contractor", location)

    phone_map = {}
    for y in yelp_results:
        if y["phone_e164"]:
            key = (y["name"].lower(), y["address"].lower())
            phone_map[key] = y["phone_e164"]

    final = []
    for g in google_results:
        key = (g["name"].lower(), g["address"].lower())
        phone = phone_map.get(key)

        if not phone:
            continue   # 🚫 NO PHONE = NO VENDOR

        g["phone_e164"] = phone
        g["supports_whatsapp"] = not phone.startswith("+1")
        final.append(g)

    return final

if __name__ == "__main__":
    vendors = merge_google_yelp(
        trades=["plumbing"],
        location="San Jose, CA"
    )

    for v in vendors:
        print(v)
