import re
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.vendor_pricing_normalizer import normalize_price

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)


async def parse_material_bid(material_bid_id: int, db: AsyncSession):
    """
    Parse inbound vendor email into normalized bid data.
    Supports international sourcing (CN, BR, etc).
    """

    result = await db.execute(
        text("""
            SELECT
                mb.raw_message,
                COALESCE(s.country_code, 'US') AS country_code
            FROM material_bids mb
            LEFT JOIN suppliers s ON s.id = mb.supplier_id
            WHERE mb.id = :id
        """),
        {"id": material_bid_id},
    )

    bid = result.mappings().first()
    if not bid:
        return

    text_body = bid["raw_message"] or ""
    country = bid["country_code"] or "US"

    prices = PRICE_RE.findall(text_body)
    lead = LEAD_RE.search(text_body)

    unit_price = prices[0].replace(",", "") if prices else None
    pricing = normalize_price(unit_price, country) if unit_price else {}

    # Update bid with normalized pricing
    await db.execute(
        text("""
            UPDATE material_bids
            SET
                status = 'parsed',
                source_country = :country,
                fx_rate = :fx,
                landed_unit_price = :landed
            WHERE id = :id
        """),
        {
            "id": material_bid_id,
            "country": country,
            "fx": pricing.get("fx_rate"),
            "landed": pricing.get("landed_unit_price"),
        },
    )

    # Store parsed line item
    await db.execute(
        text("""
            INSERT INTO material_bid_items
            (material_bid_id, notes, unit_price, lead_time)
            VALUES (:bid_id, :notes, :price, :lead)
        """),
        {
            "bid_id": material_bid_id,
            "notes": text_body[:500],
            "price": unit_price,
            "lead": lead.group(0) if lead else None,
        },
    )

    await db.commit()