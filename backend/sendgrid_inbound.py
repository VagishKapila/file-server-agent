from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhooks/sendgrid/inbound")
async def inbound_email(req: Request):
    form = await req.form()

    sg_message_id = form.get("sg_message_id")
    body = form.get("text", "")
    from_email = form.get("from")

    if not sg_message_id:
        return {"status": "missing_message_id"}

    outreach = db.fetch_one("""
        SELECT id FROM supplier_outreach
        WHERE message_id = %s
        LIMIT 1
    """, (sg_message_id,))

    if not outreach:
        return {"status": "ignored"}

    db.execute("""
        INSERT INTO supplier_responses
        (supplier_outreach_id, raw_message)
        VALUES (%s,%s)
    """, (outreach["id"], body))

    db.execute("""
        UPDATE supplier_outreach
        SET status='replied'
        WHERE id=%s
    """, (outreach["id"],))

    return {"status": "ok"}
