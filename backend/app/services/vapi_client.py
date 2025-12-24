import os
import httpx
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("vapi-client")

VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

# ✅ CORRECT + VERIFIED ENDPOINT
VAPI_CALL_URL = "https://api.vapi.ai/call"


async def start_call(phone_number: str, context: dict):
    if not VAPI_PRIVATE_KEY:
        raise RuntimeError("VAPI_PRIVATE_KEY missing")

    if not VAPI_ASSISTANT_ID:
        raise RuntimeError("VAPI_ASSISTANT_ID missing")

    if not VAPI_PHONE_NUMBER_ID:
        raise RuntimeError("VAPI_PHONE_NUMBER_ID missing")

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {
            "number": phone_number
        },
        "assistantOverrides": {
            "firstMessage": context.pop("__firstMessage", None),
            "context": context,
        },
    }

    headers = {
        "Authorization": f"Bearer {VAPI_PRIVATE_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            VAPI_CALL_URL,
            json=payload,
            headers=headers,
        )

    if response.status_code >= 300:
        raise RuntimeError(f"VAPI call failed: {response.text}")

    return response.json()