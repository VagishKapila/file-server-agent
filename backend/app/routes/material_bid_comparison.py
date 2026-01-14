from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db import get_db

router = APIRouter(prefix="/material-bids", tags=["Bid Comparison"])


@router.get("/compare/{project_id}")
async def compare_bids(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Normalized bid comparison per project.
    Uses actual schema (no assumptions).
    """

    result = await db.execute(
        text("""
            SELECT
                mb.id                AS material_bid_id,
                mb.vendor_email,
                mbi.unit_price,
                mbi.lead_time,
                mb.status,
                mb.created_at
            FROM material_bids mb
            JOIN material_requests mr
                ON mr.id = mb.material_request_id
            LEFT JOIN material_bid_items mbi
                ON mbi.material_bid_id = mb.id
            WHERE mr.project_request_id = :pid
            ORDER BY
                mbi.unit_price ASC NULLS LAST,
                mb.created_at DESC
        """),
        {"pid": project_id},
    )

    rows = result.mappings().all()

    return {
        "project_id": project_id,
        "count": len(rows),
        "bids": rows,
    }