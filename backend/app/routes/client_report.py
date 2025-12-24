from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import os
import smtplib
from email.message import EmailMessage

from backend.app.db import get_db
from backend.app.models.activity_log import ActivityLog
from backend.app.models.vendor_call_state import VendorCallState
from backend.app.models.project_files import ProjectFile
from backend.app.models.email_log import EmailLog

router = APIRouter(prefix="/client-report", tags=["client-report"])


def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)


@router.post("/send/{project_request_id}")
async def send_client_report(
    project_request_id: int,
    client_email: str,
    db: AsyncSession = Depends(get_db),
):
    # -------------------------
    # Fetch vendor outcomes
    # -------------------------
    rows = await db.execute(
        select(VendorCallState)
        .where(VendorCallState.project_request_id == project_request_id)
    )
    states = rows.scalars().all()

    if not states:
        raise HTTPException(status_code=404, detail="No call activity found")

    # -------------------------
    # Fetch files (links only)
    # -------------------------
    files = await db.execute(
        select(ProjectFile)
        .where(ProjectFile.project_request_id == project_request_id)
    )

    file_links = []
    for f in files.scalars():
        file_links.append(f"- {f.filename}: {f.stored_path}")

    # -------------------------
    # Build report body
    # -------------------------
    lines = []
    for s in states:
        lines.append(
            f"""
Vendor Phone: {s.vendor_phone}
Trade: {s.trade}
Status: {s.status}
Attempts: {s.attempts}
"""
        )

    body = f"""
Client Outreach Summary
Project ID: {project_request_id}

--- Call Results ---
{''.join(lines)}

--- Project Files ---
{chr(10).join(file_links)}

This is an automated summary from Jessica AI.
"""

    send_email(
        to_email=client_email,
        subject="Subcontractor Outreach Summary",
        body=body,
    )

    db.add(
        EmailLog(
            project_request_id=project_request_id,
            recipient_email=client_email,
            email_type="client",
            related_call_id=None,
        )
    )
    await db.commit()

    return {"status": "sent"}
