from fastapi import APIRouter, Request
from app.db import database
from app.services.client_reply_forwarder import forward_vendor_reply_to_client

router = APIRouter()

@router.post("/webhooks/sendgrid/inbound")
async def inbound_email(req: Request):
    form = await req.form()

    sg_message_id = form.get("sg_message_id")
    body = form.get("text") or form.get("html") or ""
    from_email = form.get("from", "")
    subject = form.get("subject", "")

    if not sg_message_id:
        return {"status": "missing_message_id"}

    # 1️⃣ Find outreach by SendGrid message id
    outreach = await database.fetch_one("""
        SELECT id, project_id
        FROM supplier_outreach
        WHERE message_id = :msg
        LIMIT 1
    """, {"msg": sg_message_id})

    if not outreach:
        return {"status": "ignored"}

    # 2️⃣ Save vendor response
    await database.execute("""
        INSERT INTO supplier_responses
        (supplier_outreach_id, raw_message)
        VALUES (:oid, :body)
    """, {
        "oid": outreach["id"],
        "body": body
    })

    await database.execute("""
        UPDATE supplier_outreach
        SET status='replied'
        WHERE id=:id
    """, {"id": outreach["id"]})

    # 3️⃣ Fetch client email for CC
    client = await database.fetch_one("""
        SELECT up.email
        FROM project_requests pr
        JOIN user_profiles up ON up.id = pr.user_id
        WHERE pr.id = :pid
        LIMIT 1
    """, {"pid": outreach["project_id"]})

    # 4️⃣ Forward reply to client (silent CC)
    if client and client["email"]:
        await forward_vendor_reply_to_client(
            client_email=client["email"],
            vendor_email=from_email,
            subject=subject,
            body=body
        )

    return {"status": "ok"}
