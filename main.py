from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
import logging
import smtplib
from email.message import EmailMessage

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

@app.get("/__smtp_test")
def smtp_test():
    msg = EmailMessage()
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = "vaakapila@gmail.com"
    msg["Subject"] = "Railway SMTP Test"
    msg.set_content("If you received this, Railway SMTP works.")

    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
            server.send_message(msg)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

