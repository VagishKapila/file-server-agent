from app.db import database
import re


async def parse_material_bid(material_bid_id: int):
    bid = await database.fetch_one("""
        SELECT raw_message
        FROM material_bids
        WHERE id = :id
    """, {"id": material_bid_id})

    if not bid or not bid["raw_message"]:
        return

    text = bid["raw_message"].lower()

    price_match = re.search(r"\$?\s?(\d+(?:\.\d+)?)\s?(per|/)\s?(sqft|sf|unit)", text)
    lead_time_match = re.search(r"(\d+\s?[-–]?\s?\d*)\s?(weeks|days)", text)
    moq_match = re.search(r"(minimum|moq).*?(\d+)", text)

    await database.execute("""
        INSERT INTO material_bid_items
        (material_bid_id, unit_price, lead_time, notes)
        VALUES (:bid_id, :price, :lead_time, :notes)
    """, {
        "bid_id": material_bid_id,
        "price": price_match.group(1) if price_match else None,
        "lead_time": lead_time_match.group(0) if lead_time_match else None,
        "notes": moq_match.group(0) if moq_match else None
    })

    await database.execute("""
        UPDATE material_bids
        SET status = 'parsed'
        WHERE id = :id
    """, {"id": material_bid_id})
