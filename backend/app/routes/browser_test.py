from fastapi import APIRouter
import os
import requests

router = APIRouter(prefix="/browser-test", tags=["Browser Test"])

# 🔐 MUST BE PRIVATE KEY
VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

@router.post("/jessica-call")
def jessica_call():
    if not VAPI_PRIVATE_KEY:
        return {"error": "VAPI_PRIVATE_KEY missing"}
    if not VAPI_ASSISTANT_ID or not VAPI_PHONE_NUMBER_ID:
        return {"error": "Assistant or phone number missing"}

    # ✅ CORRECT ENDPOINT
    url = "https://api.vapi.ai/call/phone"

    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": "+14084106151"
        },
        "assistantOverrides": {
            "firstMessage": "Jessica browser baseline test"
        }
    }

    res = requests.post(url, headers=headers, json=payload, timeout=15)

    return {
        "status_code": res.status_code,
        "response": res.text
    }