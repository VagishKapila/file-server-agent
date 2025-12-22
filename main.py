from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
import os
import logging
import smtplib
from email.message import EmailMessage
import urllib.request
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway-webhook")

app = FastAPI(title="Railway Webhook Relay")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================
# MODELS
# =====================================================
class BrowserEmailRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    body: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)


# =====================================================
# HELPERS
# =====================================================
def _is_valid_email(v: str) -> bool:
    if not v:
        return False
    v = v.strip()
    if "@" not in v:
        return False
    if " " in v:
        return False
    return True


def _safe_env(name: str) -> str:
    val = os.getenv(name, "")
    if not val:
        return ""
    if len(val) <= 6:
        return "***"
    return val[:3] + "***" + val[-3:]


# =====================================================
# EMAIL SENDER (WITH URL ATTACHMENTS)
# =====================================================
def send_email_with_attachments(to_email: str, subject: str, body: str, attachments=None) -> Dict[str, Any]:
    to_email = (to_email or "").strip()

    if not _is_valid_email(to_email):
        raise HTTPException(status_code=422, detail="Invalid to_email")

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_host or not smtp_user or not smtp_pass:
        raise HTTPException(status_code=500, detail="Missing SMTP environment variables")

    # IMPORTANT: for Gmail SMTP, envelope and From should match the authenticated user
    from_email = (os.getenv("FROM_EMAIL") or smtp_user).strip()

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject or "Project Files"
    msg.set_content(body or "Please see attached files.")

    attachments = attachments or []
    attached_files = []

    for a in attachments:
        url = (a.get("url") or "").strip()
        filename = (a.get("filename") or "attachment").strip()

        if not url:
            logger.error("Attachment skipped, missing url")
            continue

        try:
            with urllib.request.urlopen(url, timeout=20) as resp:
                file_bytes = resp.read()

            msg.add_attachment(
                file_bytes,
                maintype="application",
                subtype="octet-stream",
                filename=filename,
            )

            attached_files.append(filename)
            logger.info("Attached file=%s url=%s bytes=%s", filename, url, len(file_bytes))

        except Exception as e:
            logger.error("Attachment failed url=%s error=%s", url, e)

    logger.info(
        "SMTP sending to=%s from=%s smtp_user=%s host=%s port=%s attachments=%s",
        to_email,
        from_email,
        _safe_env("SMTP_USER"),
        smtp_host,
        smtp_port,
        attached_files,
    )

    # send_message returns a dict of refused recipients. empty dict means accepted by SMTP server
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)

        refused = server.send_message(msg)

    if refused:
        logger.error("SMTP refused recipients=%s", refused)
        raise HTTPException(status_code=502, detail={"smtp_refused": refused})

    logger.info("Email accepted by SMTP server to=%s attachments=%s", to_email, attached_files)
    return {"ok": True, "to_email": to_email, "attachments": attached_files}


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
        "smtp_user_set": bool(os.getenv("SMTP_USER")),
        "from_email_set": bool(os.getenv("FROM_EMAIL")),
    }

@app.get("/__smtp_health")
def smtp_health():
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")

    if not smtp_host or not smtp_user or not smtp_pass:
        return {"ok": False, "error": "Missing SMTP env vars"}

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            code, msg = server.noop()
        return {"ok": True, "noop_code": code, "noop_msg": str(msg)}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================
# RETELL WEBHOOK
# =====================================================
@app.post("/negotiator/webhook")
async def negotiator_webhook(request: Request):
    payload = await request.json()
    logger.info("WEBHOOK RECEIVED keys=%s", list(payload.keys()))

    call = payload.get("call", {})
    analysis = call.get("call_analysis", {})
    custom = analysis.get("custom_analysis_data", {})

    email = custom.get("email")
    email_confirmed = custom.get("Email Confirmed") or custom.get("email_confirmed")
    interest = custom.get("interest")

    attachments = (
        custom.get("attachments")
        or payload.get("assistantOverrides", {}).get("context", {}).get("attachments")
        or []
    )

    logger.info(
        "PARSED email=%s confirmed=%s interest=%s attachment_count=%s",
        email,
        email_confirmed,
        interest,
        len(attachments),
    )

    if email and email_confirmed:
        send_email_with_attachments(
            to_email=email,
            subject="Project Drawings and Photos - BAINS Development",
            body="Thanks for confirming your email. Attached are the drawings and photos discussed.",
            attachments=attachments,
        )

    return {"ok": True}


# =====================================================
# BROWSER FORM → EMAIL + ATTACHMENTS
# =====================================================
@app.post("/browser/send-email")
def browser_send_email(payload: BrowserEmailRequest):
    logger.info("BROWSER EMAIL REQUEST to=%s attachment_count=%s", payload.to_email, len(payload.attachments))

    result = send_email_with_attachments(
        to_email=payload.to_email,
        subject=payload.subject or "Project Drawings and Photos",
        body=payload.body or "Please find drawings and photos attached.",
        attachments=payload.attachments,
    )
    return result
