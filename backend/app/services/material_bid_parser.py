import re
from app.db import database

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)

async def parse_material_bid(material_bid_id: int):
    bid = await database.fetch_one("""
        SELECT raw_message FROM material_bids
        WHERE id = :id
    """, {"id": material_bid_id})

    if not bid:
        return

    text = bid["raw_message"]

    prices = PRICE_RE.findall(text)
    lead = LEAD_RE.search(text)

    await database.execute("""
        UPDATE material_bids
        SET status='parsed'
        WHERE id=:id
    """, {"id": material_bid_id})

    # Save parsed summary
    await database.execute("""
        INSERT INTO material_bid_items
        (material_bid_id, notes, unit_price, lead_time)
        VALUES (:bid_id, :notes, :price, :lead)
    """, {
        "bid_id": material_bid_id,
        "notes": text[:500],
        "price": prices[0].replace(",", "") if prices else None,
        "lead": lead.group(0) if lead else None
    })
