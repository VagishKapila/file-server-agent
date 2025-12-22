from fastapi import FastAPI

app = FastAPI(title="Jessica Sub AI Backend")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/__fingerprint")
def fingerprint():
    return {"status": "root main loaded"}
