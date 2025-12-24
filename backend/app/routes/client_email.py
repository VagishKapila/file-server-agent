# backend/app/routes/client_email.py

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.app.db import get_db
from backend.app.utils.email_sender import send_email
from backend.app.models.activity_log import ActivityLog
from backend.app.models.email_log import EmailLog
import logging

logger = logging.getLogger("client_email")

router = APIRouter(prefix="/email/client", tags=["email"])


class ClientEmailRequest(BaseModel):
    project_request_id: int
    client_email: str


@router.post("/send")
async def send_client_summary_email(
    payload: ClientEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.error("🔥 CLIENT EMAIL ROUTE HIT 🔥 payload=%s", payload)
    
    result = await db.execute(
        select(ActivityLog)
        .where(ActivityLog.project_id == str(payload.project_request_id))
        .where(ActivityLog.action == "contractor_search")
    )
    calls = result.scalars().all()

    html = "<h3>Contractor Search Summary</h3>"
    for c in calls:
        trade = c.payload.get("trade", [])
        address = c.payload.get("address", "N/A")
        count = c.payload.get("results_count", 0)

        html += f"""
        <p>
        <strong>Trade:</strong> {', '.join(trade)}<br/>
        <strong>Address:</strong> {address}<br/>
        <strong>Contractors Found:</strong> {count}
        </p>
        """

    send_email(
        to_email=payload.client_email,
        subject="Outreach Summary",
        html_body=html,
    )

    db.add(
        EmailLog(
            project_request_id=payload.project_request_id,
            recipient_email=payload.client_email,
            email_type="client",
        )
    )
    await db.commit()

    return {"status": "sent"}
