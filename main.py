from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway-webhook")

app = FastAPI(title="Railway Webhook Relay")

# -------------------------
# HEALTH / SANITY
# -------------------------
@app.get("/")
def root():
    return {"status": "railway server running"}

@app.get("/__fingerprint")
def fingerprint():
    return {
        "service": "railway-webhook",
        "purpose": "receive webhooks + send email",
        "database": bool(os.getenv("DATABASE_URL")),
    }

# -------------------------
# TEST ENDPOINT
# -------------------------
@app.get("/test-attachment")
def test_attachment():
    return {"ok": True, "message": "Attachment endpoint reachable"}

# -------------------------
# VAPI / WAPI WEBHOOK
# -------------------------
@app.post("/negotiator/webhook")
async def negotiator_webhook(request: Request):
    payload = await request.json()

    logger.info("📥 WEBHOOK RECEIVED")
    logger.info(payload)

    # 🔴 FOR NOW: just acknowledge
    # Later: insert into DB + trigger email
    return {"ok": True}
