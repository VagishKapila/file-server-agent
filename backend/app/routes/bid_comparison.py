from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.db import get_db
from app.services.bid_ranker import rank_bids

router = APIRouter(prefix="/bids", tags=["Bid Comparison"])

@router.get("/compare/{project_id}")
async def compare_bids(project_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("""
            SELECT
                mb.id,
                mb.vendor_email,
                mb.source_country,
                mb.landed_unit_price,
                mbi.lead_time,
                mr.material_name,
                mr.quantity,
                mr.unit
            FROM material_bids mb
            JOIN material_bid_items mbi ON mbi.material_bid_id = mb.id
            JOIN material_requests mr ON mr.id = mb.material_request_id
            WHERE mb.project_id = :pid
        """),
        {"pid": project_id},
    )

    bids = result.mappings().all()
    return rank_bids(bids)
