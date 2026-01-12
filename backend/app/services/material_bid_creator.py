from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal


async def create_material_bid_from_email(inbound_email_id: int):
    """
    Convert a matched inbound email into a material bid
    """

    async with AsyncSessionLocal() as session:  # type: AsyncSession

        # 1️⃣ Fetch inbound email (must be matched to a project)
        result = await session.execute(
            text("""
                SELECT *
                FROM inbound_emails
                WHERE id = :id
                  AND project_request_id IS NOT NULL
            """),
            {"id": inbound_email_id},
        )
        email = result.mappings().first()

        if not email:
            return None

        # 2️⃣ Prevent duplicate bids
        result = await session.execute(
            text("""
                SELECT id
                FROM material_bids
                WHERE inbound_email_id = :id
            """),
            {"id": inbound_email_id},
        )
        existing = result.mappings().first()

        if existing:
            return existing["id"]

        # 3️⃣ Create material bid
        result = await session.execute(
            text("""
                INSERT INTO material_bids
                (
                    material_request_id,
                    vendor_email,
                    inbound_email_id,
                    raw_message,
                    status
                )
                VALUES
                (
                    :material_request_id,
                    :vendor_email,
                    :inbound_email_id,
                    :raw_message,
                    'received'
                )
                RETURNING id
            """),
            {
                "material_request_id": email["material_request_id"],
                "vendor_email": email["from_email"],
                "inbound_email_id": inbound_email_id,
                "raw_message": email["raw_text"] or email["raw_html"],
            },
        )

        bid_id = result.scalar_one()

        # 4️⃣ Mark inbound email as processed
        await session.execute(
            text("""
                UPDATE inbound_emails
                SET status = 'processed'
                WHERE id = :id
            """),
            {"id": inbound_email_id},
        )

        await session.commit()

        return bid_id