from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db

router = APIRouter(prefix="/material-bids", tags=["Bid Comparison"])


@router.get("/compare/{project_id}")
async def compare_bids(project_id: int, db: AsyncSession = Depends(get_db)):
    """
    Normalized bid comparison per project
    """

    result = await db.execute(
        text("""
            SELECT
                mb.vendor_email,
                mbi.material_name,
                mbi.quantity,
                mbi.unit,
                mbi.unit_price,
                mbi.total_price,
                mbi.lead_time
            FROM material_bid_items mbi
            JOIN material_bids mb ON mb.id = mbi.material_bid_id
            JOIN inbound_emails ie ON ie.id = mb.inbound_email_id
            WHERE ie.project_request_id = :pid
            ORDER BY mbi.total_price NULLS LAST
        """),
        {"pid": project_id},
    )

    return result.mappings().all()
