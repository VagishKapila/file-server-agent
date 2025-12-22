from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/__fingerprint")
def fingerprint():
    return {"status": "root main loaded"}

# 🔥 TEMP TEST
@app.get("/test-attachment")
def test_attachment():
    return PlainTextResponse("ATTACHMENT OK")
