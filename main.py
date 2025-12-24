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
from pathlib import Path
import requests

from autodial import router as autodial_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway-webhook")

app = FastAPI(title="Railway Webhook Relay")
app.include_router(autodial_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------- MODELS ----------------
class BrowserEmailRequest(BaseModel):
    to_email: str
    subject: Optional[str] = None
    body: Optional[str] = None
    attachments: List[Dict[str, Any]] = Field(default_factory=list)

# ---------------- HEALTH ----------------
@app.get("/")
def root():
    return {"status": "railway autodial running"}

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/__env_check")
def env_check():
    return {
        "RETELL_API_KEY": bool(os.getenv("RETELL_API_KEY")),
        "RETELL_AGENT_ID": bool(os.getenv("RETELL_AGENT_ID")),
        "RETELL_PHONE_NUMBER": bool(os.getenv("RETELL_PHONE_NUMBER")),
    }

@app.post("/retell/webhook")
async def retell_webhook_proxy(request: Request):
    payload = await request.json()

    # forward to backend app
    r = requests.post(
        os.getenv("BACKEND_BASE_URL") + "/retell/webhook",
        json=payload,
        timeout=10
    )

    if r.status_code >= 400:
        raise HTTPException(status_code=500, detail="Backend webhook failed")

    return {"ok": True}
