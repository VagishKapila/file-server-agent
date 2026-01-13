from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
import logging

logger = logging.getLogger(__name__)


async def record_vendor_signal(
    db: AsyncSession,
    vendor_email: str,
    signal: str,
    project_request_id: int | None = None,
):
    """
    Derived vendor reputation signal.
    NO scoring, NO new tables.
    Uses existing data for future weighting.
    """

    # Example signals we care about (expand later):
    # - material_bid_received
    # - material_bid_parsed
    # - attachment_provided

    await db.execute(
        text("""
            INSERT INTO activity_log
            (
                entity_type,
                entity_key,
                action,
                metadata
            )
            VALUES
            (
                'vendor',
                :vendor_email,
                :action,
                jsonb_build_object(
                    'project_request_id', :project_request_id
                )
            )
        """),
        {
            "vendor_email": vendor_email,
            "action": signal,
            "project_request_id": project_request_id,
        },
    )