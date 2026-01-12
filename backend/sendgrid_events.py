from fastapi import APIRouter, Request

router = APIRouter()

@router.post("/webhooks/sendgrid/events")
async def sendgrid_events(req: Request):
    events = await req.json()

    for event in events:
        message_id = event.get("sg_message_id")
        event_type = event.get("event")

        if not message_id:
            continue

        if event_type in ["bounce", "dropped"]:
            db.execute("""
                UPDATE supplier_outreach
                SET status='bounced'
                WHERE message_id=%s
            """, (message_id,))

        if event_type == "delivered":
            db.execute("""
                UPDATE supplier_outreach
                SET status='delivered'
                WHERE message_id=%s
            """, (message_id,))

    return {"status": "ok"}
