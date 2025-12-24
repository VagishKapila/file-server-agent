import os
import httpx
import logging
from datetime import datetime

logger = logging.getLogger("test-single-call")
logging.basicConfig(level=logging.INFO)

VAPI_PRIVATE_KEY = os.getenv("VAPI_PRIVATE_KEY")
VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")

VAPI_BASE_URL = "https://api.vapi.ai/call"


async def trigger_test_call(
    *,
    phone: str,
    trade: str,
    project_address: str,
    callback_phone: str | None = None,
):
    """
    🔥 TEST-ONLY CALL
    - Calls ONE number
    - No retries
    - No DB
    - No vendor loops
    """

    if not phone.startswith("+"):
        phone = "+" + phone

    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,
        "customer": {"number": phone},
        "assistantOverrides": {
            "firstMessage": (
                f"Hi, this is Jessica from BAINS Development. "
                f"We have a {trade} project coming up at {project_address}. "
                f"Are you currently taking on new work?"
            ),
            "context": {
                "project_address": project_address,
                "trade": trade,
                "callback_phone": callback_phone,
                "test_mode": True,
                "timestamp": datetime.utcnow().isoformat(),
                "email_capture_instruction": (
                    "If the vendor confirms interest or says yes, "
                    "you MUST ask: "
                    "Great — what is the best email address to send the drawings to? "
                    "Do not proceed until an email is collected or the vendor refuses."
                ),
            },
        },
    }

    headers = {
        "Authorization": f"Bearer {os.getenv('VAPI_PRIVATE_KEY')}"
        "Content-Type": "application/json",
    }

    logger.info("📞 TEST CALL → %s | trade=%s", phone, trade)

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(VAPI_BASE_URL, json=payload, headers=headers)

    if resp.status_code >= 300:
        logger.error("❌ VAPI test call failed: %s", resp.text)
        return False

    logger.info("✅ TEST CALL SENT SUCCESSFULLY")
    return True
