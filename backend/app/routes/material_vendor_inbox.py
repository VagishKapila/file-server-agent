from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db

router = APIRouter(prefix="/material-inbox", tags=["Material Inbox"])


@router.get("/project/{project_id}")
async def get_project_vendor_inbox(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Threaded vendor inbox per project.
    Includes outbound requests + inbound replies + bid status.
    """

    result = await db.execute(
        text("""
            SELECT
                so.id               AS outreach_id,
                so.to_email         AS vendor_email,
                so.subject          AS outbound_subject,
                so.created_at       AS outbound_at,
                so.status           AS outreach_status,

                ie.id               AS inbound_email_id,
                ie.received_at      AS inbound_at,
                ie.subject          AS inbound_subject,
                ie.raw_text         AS inbound_text,
                ie.raw_html         AS inbound_html,

                mb.id               AS material_bid_id,
                mb.status           AS bid_status

            FROM supplier_outreach so
            LEFT JOIN inbound_emails ie
                ON ie.message_id = so.message_id
            LEFT JOIN material_bids mb
                ON mb.inbound_email_id = ie.id

            WHERE so.project_id = :project_id
            ORDER BY COALESCE(ie.received_at, so.created_at) DESC
        """),
        {"project_id": project_id},
    )

    return result.mappings().all()
