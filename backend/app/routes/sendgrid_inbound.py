from fastapi import APIRouter, Request, HTTPException
from pathlib import Path
import os
import uuid
import shutil
from datetime import datetime

from app.db import database  # assumes async db wrapper you already use

router = APIRouter()

UPLOAD_DIR = os.getenv("UPLOAD_DIR")
if not UPLOAD_DIR:
    raise RuntimeError("UPLOAD_DIR not set")

BASE_INBOUND_DIR = Path(UPLOAD_DIR) / "inbound_emails"
BASE_INBOUND_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/sendgrid/inbound")
async def sendgrid_inbound(request: Request):
    """
    Primary SendGrid Inbound Parse webhook
    """
    form = await request.form()

    # ---- Core fields ----
    message_id = form.get("headers")
    from_email = form.get("from")
    to_email = form.get("to")
    subject = form.get("subject")
    text = form.get("text")
    html = form.get("html")

    received_at = datetime.utcnow()

    # ---- Insert inbound_emails ----
    insert_email_query = """
        INSERT INTO inbound_emails
        (message_id, from_email, to_email, subject, raw_text, raw_html, received_at)
        VALUES (:message_id, :from_email, :to_email, :subject, :raw_text, :raw_html, :received_at)
        RETURNING id
    """

    inbound_email_id = await database.fetch_val(
        insert_email_query,
        {
            "message_id": message_id,
            "from_email": from_email,
            "to_email": to_email,
            "subject": subject,
            "raw_text": text,
            "raw_html": html,
            "received_at": received_at,
        }
    )

    # ---- File system path ----
    email_dir = BASE_INBOUND_DIR / str(inbound_email_id)
    attachments_dir = email_dir / "attachments"
    attachments_dir.mkdir(parents=True, exist_ok=True)

    # ---- Save attachments ----
    for key, value in form.items():
        if hasattr(value, "filename") and value.filename:
            file_id = str(uuid.uuid4())
            safe_name = value.filename.replace("/", "_")
            file_path = attachments_dir / f"{file_id}_{safe_name}"

            with open(file_path, "wb") as f:
                shutil.copyfileobj(value.file, f)

            insert_attachment_query = """
                INSERT INTO inbound_attachments
                (inbound_email_id, filename, file_path, content_type, file_size)
                VALUES (:inbound_email_id, :filename, :file_path, :content_type, :file_size)
            """

            await database.execute(
                insert_attachment_query,
                {
                    "inbound_email_id": inbound_email_id,
                    "filename": safe_name,
                    "file_path": str(file_path),
                    "content_type": value.content_type,
                    "file_size": file_path.stat().st_size,
                }
            )

    return {"status": "ok"}
