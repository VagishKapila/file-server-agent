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
    result = await db.execute(
        text("""
            SELECT
                ie.id AS inbound_email_id,
                ie.from_email,
                ie.subject,
                ie.received_at,
                mb.id AS material_bid_id,
                mb.status,
                mb.raw_message
            FROM inbound_emails ie
            LEFT JOIN material_bids mb ON mb.inbound_email_id = ie.id
            WHERE ie.project_request_id = :project_id
            ORDER BY ie.received_at DESC
        """),
        {"project_id": project_id},
    )

    return result.mappings().all()