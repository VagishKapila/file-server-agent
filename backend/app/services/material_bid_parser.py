import re
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.vendor_pricing_normalizer import normalize_price

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)


async def parse_material_bid(
    material_bid_id: int,
    db: AsyncSession,
):
    """
    Parse pricing + lead time from vendor email
    and persist normalized bid items.
    """

    # ------------------------------------------------------------
    # 1️⃣ Fetch material bid + supplier context
    # ------------------------------------------------------------
    result = await db.execute(
        text("""
            SELECT
                mb.raw_message,
                s.country_code
            FROM material_bids mb
            LEFT JOIN suppliers s ON s.email = mb.vendor_email
            WHERE mb.id = :id
        """),
        {"id": material_bid_id},
    )
    bid = result.mappings().first()

    if not bid:
        logger.warning(
            "Material bid not found for parsing",
            extra={"material_bid_id": material_bid_id},
        )
        return

    text_body = bid["raw_message"] or ""
    country = bid["country_code"] or "US"

    # ------------------------------------------------------------
    # 2️⃣ Extract pricing + lead time
    # ------------------------------------------------------------
    prices = PRICE_RE.findall(text_body)
    lead = LEAD_RE.search(text_body)

    unit_price = prices[0].replace(",", "") if prices else None
    pricing = normalize_price(unit_price, country) if unit_price else {}

    # ------------------------------------------------------------
    # 3️⃣ Update material_bids summary
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 4️⃣ Insert material_bid_items
    # ------------------------------------------------------------
    await db.execute(
        text("""
            INSERT INTO material_bid_items
            (
                material_bid_id,
                notes,
                unit_price,
                lead_time
            )
            VALUES
            (
                :bid_id,
                :notes,
                :price,
                :lead
            )
        """),
        {
            "bid_id": material_bid_id,
            "notes": text_body[:500],
            "price": unit_price,
            "lead": lead.group(0) if lead else None,
        },
    )

    await db.commit()