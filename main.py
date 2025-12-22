from fastapi import FastAPI, Request
from dotenv import load_dotenv
import os
import logging
import smtplib
from email.message import EmailMessage
import urllib.request
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway-webhook")

app = FastAPI(title="Railway Webhook Relay")

class BrowserEmailRequest(BaseModel):
    to_email: str
    attachments: list = []

# =====================================================
# EMAIL SENDER (WITH URL ATTACHMENTS)
# =====================================================
def send_email_with_attachments(to_email, subject, body, attachments=None):
    msg = EmailMessage()
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    attachments = attachments or []

    for a in attachments:
        try:
            with urllib.request.urlopen(a["url"], timeout=10) as resp:
                file_bytes = resp.read()

            msg.add_attachment(
                file_bytes,
                maintype="application",
                subtype="octet-stream",
                filename=a.get("filename", "attachment")
            )

            logger.info("📎 Attached: %s", a["url"])

        except Exception as e:
            logger.error("❌ Attachment failed: %s | %s", a["url"], e)

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)

    logger.info("✅ Email sent to %s", to_email)


# =====================================================
# HEALTH / SANITY
# =====================================================
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

# =====================================================
# BASIC TEST ENDPOINT
# =====================================================
@app.get("/test-attachment")
def test_attachment():
    return {"ok": True, "message": "Attachment endpoint reachable"}

# =====================================================
# BROWSER EMAIL + ATTACHMENT TEST (NO WEBHOOK)
# =====================================================
@app.get("/__attachment_test")
def attachment_test():
    send_email_with_attachments(
        to_email="vaakapila@gmail.com",
        subject="Railway Attachment Test",
        body="If you got this email WITH attachment, everything works.",
        attachments=[
            {
                "filename": "sample.txt",
                "url": "https://raw.githubusercontent.com/github/gitignore/main/Python.gitignore"
            }
        ]
    )
    return {"ok": True, "sent": True}

# =====================================================
# SMTP ONLY TEST (NO ATTACHMENTS)
# =====================================================
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

# =====================================================
# VAPI / WAPI WEBHOOK (NOW SENDS EMAIL + ATTACHMENTS)
# =====================================================
@app.post("/negotiator/webhook")
async def negotiator_webhook(request: Request):
    payload = await request.json()
    logger.info("📥 WEBHOOK RECEIVED")
    logger.info(payload)

    # ---- VAPI extraction (SAFE + MINIMAL) ----
    email = None
    attachments = []

    try:
        email = payload["call"]["artifact"]["structuredOutputs"][0]["output"].get("email")
        attachments = payload.get("assistantOverrides", {}).get("context", {}).get("attachments", [])
    except Exception as e:
        logger.error("❌ Payload parse failed: %s", e)

    if email:
        send_email_with_attachments(
            to_email=email,
            subject="VAPI Project Files",
            body="Please find the attached files.",
            attachments=attachments
        )

    return {"ok": True}

# =====================================================
# BROWSER FORM → EMAIL + ATTACHMENTS
# =====================================================
@app.post("/browser/send-email")
def browser_send_email(payload: BrowserEmailRequest):
    logger.info("🌐 BROWSER EMAIL REQUEST")
    logger.info(payload.dict())

    send_email_with_attachments(
        to_email=payload.to_email,
        subject="Project Drawings & Photos",
        body="Please find drawings and photos attached.",
        attachments=payload.attachments,
    )

    return {"ok": True}
