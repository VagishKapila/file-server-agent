from fastapi import FastAPI, Request, HTTPException
from dotenv import load_dotenv
import os
import logging
import requests   # ✅ REQUIRED
from fastapi.middleware.cors import CORSMiddleware

from autodial import router as autodial_router
from app.routes.debug_files import router as debug_files_router

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("railway-webhook")

app = FastAPI(title="Railway Webhook Relay")

# ---------------- ROUTERS ----------------
app.include_router(autodial_router)

# ---------------- MIDDLEWARE ----------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        "BACKEND_BASE_URL": os.getenv("BACKEND_BASE_URL"),
    }

# ---------------- RETELL WEBHOOK PROXY ----------------
@app.post("/retell/webhook")
async def retell_webhook_proxy(request: Request):
    payload = await request.json()

    backend_url = os.getenv("BACKEND_BASE_URL")
    if not backend_url:
        raise HTTPException(status_code=500, detail="BACKEND_BASE_URL not set")

    logger.info("➡️ Forwarding Retell webhook to backend")

    r = requests.post(
        f"{backend_url}/retell/webhook",
        json=payload,
        timeout=10,
    )

    if r.status_code >= 400:
        logger.error("❌ Backend webhook failed: %s", r.text)
        raise HTTPException(status_code=500, detail="Backend webhook failed")

    return {"ok": True}
