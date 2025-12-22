from fastapi import FastAPI
from backend.app.routes.negotiator_webhook import router as negotiator_router

app = FastAPI()

app.include_router(negotiator_router)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/__fingerprint")
def fingerprint():
    return {"status": "railway webhook server"}
