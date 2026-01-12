import re
from sqlalchemy import text
from app.db import database
from app.services.vendor_pricing_normalizer import normalize_price

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)

async def parse_material_bid(material_bid_id: int):
    bid = await database.fetch_one("""
        SELECT mb.raw_message, s.country_code
        FROM material_bids mb
        JOIN suppliers s ON s.id = mb.supplier_id
        WHERE mb.id = :id
    """, {"id": material_bid_id})

    if not bid:
        return

    text_body = bid["raw_message"]
    country = bid["country_code"] or "US"

    prices = PRICE_RE.findall(text_body)
    lead = LEAD_RE.search(text_body)

    unit_price = prices[0].replace(",", "") if prices else None
    pricing = normalize_price(unit_price, country) if unit_price else {}

    await database.execute("""
        UPDATE material_bids
        SET
            status='parsed',
            source_country=:country,
            fx_rate=:fx,
            landed_unit_price=:landed
        WHERE id=:id
    """, {
        "id": material_bid_id,
        "country": country,
        "fx": pricing.get("fx_rate"),
        "landed": pricing.get("landed_unit_price"),
    })

    await database.execute("""
        INSERT INTO material_bid_items
        (material_bid_id, notes, unit_price, lead_time)
        VALUES (:bid_id, :notes, :price, :lead)
    """, {
        "bid_id": material_bid_id,
        "notes": text_body[:500],
        "price": unit_price,
        "lead": lead.group(0) if lead else None,
    })
