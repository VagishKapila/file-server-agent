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
