from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def create_material_bid_from_email(
    inbound_email_id: int,
    db: AsyncSession,
):
    """
    Convert a matched inbound email into a material bid.
    Uses project_requests directly (no material_requests table).
    """

    # 1️⃣ Fetch inbound email (must be matched)
    result = await db.execute(
        text("""
            SELECT id, from_email, raw_text, raw_html, project_request_id
            FROM inbound_emails
            WHERE id = :id
              AND project_request_id IS NOT NULL
        """),
        {"id": inbound_email_id},
    )
    email = result.mappings().first()

    if not email:
        return None

    project_request_id = email["project_request_id"]

    # 2️⃣ Prevent duplicate material bids
    result = await db.execute(
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
    try:
        result = await db.execute(
            text("""
                INSERT INTO material_bids
                (
                    project_request_id,
                    vendor_email,
                    inbound_email_id,
                    raw_message,
                    status
                )
                VALUES
                (
                    :project_request_id,
                    :vendor_email,
                    :inbound_email_id,
                    :raw_message,
                    'received'
                )
                RETURNING id
            """),
            {
                "project_request_id": project_request_id,
                "vendor_email": email["from_email"],
                "inbound_email_id": inbound_email_id,
                "raw_message": email["raw_text"] or email["raw_html"],
            },
        )
        bid_id = result.scalar_one()

    except Exception as e:
        logger.error(
            "Failed to create material bid",
            extra={
                "inbound_email_id": inbound_email_id,
                "project_request_id": project_request_id,
                "error": str(e),
            },
        )
        return None

    # 4️⃣ Mark inbound email as processed
    await db.execute(
        text("""
            UPDATE inbound_emails
            SET status = 'processed'
            WHERE id = :id
        """),
        {"id": inbound_email_id},
    )

    await db.commit()
    return bid_id