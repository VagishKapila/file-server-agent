from fastapi import APIRouter
from app.db import database

router = APIRouter(prefix="/material-inbox")

@router.get("/{project_id}")
async def get_material_inbox(project_id: int):
    return await database.fetch_all("""
        SELECT
            mb.id AS bid_id,
            mb.vendor_email,
            mb.status,
            mbi.unit_price,
            mbi.lead_time,
            mbi.notes,
            mb.created_at
        FROM material_bids mb
        LEFT JOIN material_bid_items mbi ON mbi.material_bid_id = mb.id
        WHERE mb.material_request_id = :project_id
        ORDER BY mb.created_at DESC
    """, {"project_id": project_id})
