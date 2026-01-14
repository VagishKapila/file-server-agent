import re
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

PRICE_RE = re.compile(r"\$ ?([\d,]+(?:\.\d+)?)")
LEAD_RE = re.compile(r"(\d+[-–]?\d*)\s*(weeks|days)", re.I)


async def parse_material_bid(
    material_bid_id: int,
    db: AsyncSession,
):
    """
    Parse raw vendor email content into structured bid items.
    This version is schema-safe and does NOT depend on suppliers table.
    """

    # --------------------------------------------------------
    # 1️⃣ Fetch bid message
    # --------------------------------------------------------
    result = await db.execute(
        text("""
            SELECT
                raw_message
            FROM material_bids
            WHERE id = :id
        """),
        {"id": material_bid_id},
    )

    bid = result.mappings().first()
    if not bid:
        logger.warning("Material bid not found", extra={"id": material_bid_id})
        return

    text_body = bid["raw_message"] or ""

    # --------------------------------------------------------
    # 2️⃣ Extract pricing + lead time
    # --------------------------------------------------------
    prices = PRICE_RE.findall(text_body)
    lead = LEAD_RE.search(text_body)

    unit_price = prices[0].replace(",", "") if prices else None
    lead_time = lead.group(0) if lead else None

    # --------------------------------------------------------
    # 3️⃣ Insert parsed item (idempotent per bid)
    # --------------------------------------------------------
    await db.execute(
        text("""
            INSERT INTO material_bid_items
            (
                material_bid_id,
                unit_price,
                lead_time,
                notes
            )
            VALUES
            (
                :bid_id,
                :unit_price,
                :lead_time,
                :notes
            )
            ON CONFLICT DO NOTHING
        """),
        {
            "bid_id": material_bid_id,
            "unit_price": unit_price,
            "lead_time": lead_time,
            "notes": text_body[:500],
        },
    )

    # --------------------------------------------------------
    # 4️⃣ Update bid status + defaults
    # --------------------------------------------------------
    await db.execute(
        text("""
            UPDATE material_bids
            SET
                status = 'parsed',
                source_country = COALESCE(source_country, 'US')
            WHERE id = :id
        """),
        {"id": material_bid_id},
    )

    logger.info(
        "Material bid parsed",
        extra={
            "material_bid_id": material_bid_id,
            "unit_price": unit_price,
            "lead_time": lead_time,
        },
    )