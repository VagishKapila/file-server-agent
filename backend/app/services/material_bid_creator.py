from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.services.vendor_reputation import record_vendor_signal

logger = logging.getLogger(__name__)


async def create_material_bid_from_email(
    inbound_email_id: int,
    db: AsyncSession,
):
    """
    Convert a matched inbound email into a material bid.
    Ensures a material_request exists and links the bid to it.
    """

    # ------------------------------------------------------------
    # 1️⃣ Fetch inbound email (must be matched to project)
    # ------------------------------------------------------------
    result = await db.execute(
        text("""
            SELECT
                id,
                from_email,
                raw_text,
                raw_html,
                project_request_id
            FROM inbound_emails
            WHERE id = :id
              AND project_request_id IS NOT NULL
        """),
        {"id": inbound_email_id},
    )
    email = result.mappings().first()

    if not email:
        logger.info(
            "Inbound email not matched to project",
            extra={"id": inbound_email_id},
        )
        return None

    project_request_id = email["project_request_id"]

    # ------------------------------------------------------------
    # 2️⃣ Prevent duplicate material bids (idempotent per email)
    # ------------------------------------------------------------
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

    # ------------------------------------------------------------
    # 3️⃣ Find or create OPEN material_request
    # ------------------------------------------------------------
    result = await db.execute(
        text("""
            SELECT id
            FROM material_requests
            WHERE project_request_id = :pid
              AND status = 'open'
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"pid": project_request_id},
    )
    mr = result.first()

    if mr:
        material_request_id = mr[0]
    else:
        logger.info(
            "Creating material_request",
            extra={"project_request_id": project_request_id},
        )

        result = await db.execute(
            text("""
                INSERT INTO material_requests (
                    project_request_id,
                    source,
                    status
                )
                VALUES (
                    :pid,
                    'email_reply',
                    'open'
                )
                RETURNING id
            """),
            {"pid": project_request_id},
        )
        material_request_id = result.scalar_one()

    # ------------------------------------------------------------
    # 4️⃣ Create material bid (linked correctly)
    # ------------------------------------------------------------
    try:
        result = await db.execute(
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
                    :mrid,
                    :vendor_email,
                    :inbound_email_id,
                    :raw_message,
                    'received'
                )
                RETURNING id
            """),
            {
                "mrid": material_request_id,
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
                "error": str(e),
            },
        )
        await db.rollback()
        return None

    # ------------------------------------------------------------
    # 5️⃣ Mark inbound email as processed
    # ------------------------------------------------------------
    await db.execute(
        text("""
            UPDATE inbound_emails
            SET status = 'processed'
            WHERE id = :id
        """),
        {"id": inbound_email_id},
    )

    # ------------------------------------------------------------
    # 6️⃣ Vendor reputation signal (non-blocking)
    # ------------------------------------------------------------
    try:
        await record_vendor_signal(
            db=db,
            vendor_email=email["from_email"],
            signal="material_bid_received",
            project_request_id=project_request_id,
        )
    except Exception as e:
        logger.warning(
            "Vendor reputation signal failed",
            extra={"error": str(e)},
        )

    await db.commit()
    return bid_id