from .google_scraper import google_search

def clean_bytes(obj):
    """Remove all bytes so FastAPI never crashes when encoding JSON."""
    if isinstance(obj, bytes):
        return "<binary>"
    if isinstance(obj, dict):
        return {k: clean_bytes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [clean_bytes(i) for i in obj]
    return obj

async def search_subcontractors(trades, radius, preferred, location):

    # Convert miles → meters
    try:
        miles = int(radius.split()[0])
    except Exception:
        miles = 15

    radius_meters = miles * 1609

    # Raw Google results (may contain bytes)
    google_results = google_search(trades, location, radius_meters)

    preferred_set = {p.lower() for p in preferred}

    for result in google_results:
        name = (result.get("name") or "").lower()
        result["preferred"] = name in preferred_set

    # 🔥 Critical: remove bytes before returning
    return clean_bytes(google_results)