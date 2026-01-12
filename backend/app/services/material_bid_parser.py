import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)


async def parse_material_bid(
    material_bid_id: int,
    db: AsyncSession,
):
    result = await db.execute(
        text("""
            SELECT raw_message
            FROM material_bids
            WHERE id = :id
        """),
        {"id": material_bid_id},
    )
    bid = result.mappings().first()
    if not bid:
        return

    text_body = bid["raw_message"] or ""

    prices = PRICE_RE.findall(text_body)
    lead = LEAD_RE.search(text_body)

    await db.execute(
        text("""
            UPDATE material_bids
            SET status = 'parsed'
            WHERE id = :id
        """),
        {"id": material_bid_id},
    )

    await db.execute(
        text("""
            INSERT INTO material_bid_items
            (material_bid_id, notes, unit_price, lead_time)
            VALUES (:bid_id, :notes, :price, :lead)
        """),
        {
            "bid_id": material_bid_id,
            "notes": text_body[:500],
            "price": prices[0].replace(",", "") if prices else None,
            "lead": lead.group(0) if lead else None,
        },
    )

    await db.commit()