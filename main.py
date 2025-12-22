from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import JSONResponse
import os
from email.message import EmailMessage
import smtplib

app = FastAPI(title="Railway Webhook + Email Relay")

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/__fingerprint")
def fingerprint():
    return {"status": "railway relay running"}

@app.post("/negotiator/webhook")
async def negotiator_webhook(request: Request):
    data = await request.json()
    print("WEBHOOK RECEIVED:", data)
    return {"ok": True}

@app.post("/send-email")
async def send_email(
    to_email: str,
    file: UploadFile = File(...)
):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    msg = EmailMessage()
    msg["From"] = os.getenv("FROM_EMAIL")
    msg["To"] = to_email
    msg["Subject"] = "Test Attachment"
    msg.set_content("Attachment test")

    with open(file_path, "rb") as f:
        msg.add_attachment(
            f.read(),
            maintype="application",
            subtype="octet-stream",
            filename=file.filename,
        )

    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
        server.starttls()
        server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        server.send_message(msg)

    return {"sent": True, "file": file.filename}
