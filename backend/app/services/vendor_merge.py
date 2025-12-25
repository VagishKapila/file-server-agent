import os
import psycopg2

from google_scraper import google_search
from yelp_scraper import yelp_search


# -----------------------------
# Helpers
# -----------------------------
def normalize(text: str) -> str:
    if not text:
        return ""
    return (
        text.lower()
        .replace(",", "")
        .replace(".", "")
        .replace("&", "and")
        .strip()
    )


# -----------------------------
# DB Save
# -----------------------------
def save_vendors(vendors):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL not set")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    for v in vendors:
        cur.execute(
            """
            INSERT INTO vendors (
                name,
                trade,
                phone,
                phone_e164,
                country,
                created_by
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (
                v["name"],
                v["trade"],
                v["phone_e164"][-10:],  # raw local digits
                v["phone_e164"],
                "US" if v["phone_e164"].startswith("+1") else "INTL",
                v["source"],
            ),
        )

    conn.commit()
    cur.close()
    conn.close()


# -----------------------------
# Merge Logic
# -----------------------------
def merge_google_yelp(trades, location, radius_meters=30000):
    google_results = google_search(trades, location, radius_meters)
    yelp_results = yelp_search(trades[0], location)

    print("GOOGLE:", len(google_results))
    print("YELP:", len(yelp_results))

    # Build Yelp phone lookup (name-based)
    phone_map = {}
    for y in yelp_results:
        if not y.get("phone_e164"):
            continue

        key = normalize(y["name"])
        phone_map[key] = y["phone_e164"]

    final = []

    for g in google_results:
        key = normalize(g["name"])
        phone = phone_map.get(key)

        if not phone:
            continue  # 🚫 no phone = no vendor

        g["phone_e164"] = phone
        g["supports_whatsapp"] = not phone.startswith("+1")
        final.append(g)

    return final


# -----------------------------
# Manual Run
# -----------------------------
if __name__ == "__main__":
    vendors = merge_google_yelp(
        trades=["plumbing"],
        location="San Jose, CA",
    )

    print("FINAL:", len(vendors))
    for v in vendors[:5]:
        print(v)

    if vendors:
        save_vendors(vendors)
        print("✅ Vendors saved to DB")
    else:
        print("⚠️ No vendors with phones found")