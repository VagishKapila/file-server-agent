from fastapi import APIRouter
from app.db import database

router = APIRouter(prefix="/material-inbox", tags=["Material Inbox"])

@router.get("/project/{project_id}")
async def get_project_vendor_inbox(project_id: int):
    """
    Returns all vendor emails & replies for a project
    """
    rows = await database.fetch_all("""
        SELECT
            ie.id AS inbound_email_id,
            ie.from_email,
            ie.subject,
            ie.received_at,
            mb.id AS material_bid_id,
            mb.status,
            sr.raw_message
        FROM inbound_emails ie
        LEFT JOIN material_bids mb ON mb.inbound_email_id = ie.id
        LEFT JOIN supplier_responses sr ON sr.supplier_outreach_id = mb.id
        WHERE ie.project_request_id = :project_id
        ORDER BY ie.received_at DESC
    """, {"project_id": project_id})

    return rows
