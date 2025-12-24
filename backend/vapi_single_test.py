import os
import requests
from dotenv import load_dotenv

load_dotenv()

VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

print("ENV CHECK:")
print("VAPI_PRIVATE_KEY:", bool(VAPI_PRIVATE_KEY))
print("VAPI_ASSISTANT_ID:", VAPI_ASSISTANT_ID)
print("VAPI_PHONE_NUMBER_ID:", VAPI_PHONE_NUMBER_ID)

url = "https://api.vapi.ai/call"

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
        "firstMessage": "Jessica absolute baseline test"
    }
}

print("📞 Sending call request to VAPI...")
res = requests.post(url, headers=headers, json=payload)

print("STATUS:", res.status_code)
print("RESPONSE:", res.text)
