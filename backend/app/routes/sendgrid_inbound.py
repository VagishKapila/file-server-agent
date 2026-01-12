from fastapi import APIRouter, Request
import json
import logging

router = APIRouter(prefix="/sendgrid", tags=["sendgrid"])

@router.post("/inbound")
async def sendgrid_inbound(request: Request):
    """
    SendGrid Inbound Parse Webhook
    Receives inbound vendor emails, attachments, replies, etc.
    """
    try:
        form = await request.form()
        data = dict(form)

        logging.info("📩 SENDGRID INBOUND RECEIVED")
        logging.info(json.dumps(data, indent=2))

        # TODO (next steps):
        # - Save raw email
        # - Extract from / to / subject
        # - Attachments
        # - Match to material_request / vendor
        # - AI parsing

        return {"status": "ok"}

    except Exception as e:
        logging.exception("❌ SendGrid inbound parse error")
        return {"status": "error", "detail": str(e)}
