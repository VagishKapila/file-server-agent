import httpx
import logging
from config.vapi_config import (
    VAPI_BASE_URL,
    VAPI_ASSISTANT_ID,
    VAPI_PHONE_NUMBER_ID,
    SAFE_CALL_MODE,
    SAFE_TEST_NUMBER,
    get_vapi_private_key,
)

logger = logging.getLogger("vapi")

# ==============================
# CORE VAPI CALL ENGINE
# ==============================

async def start_call(phone_number: str, context: dict):
    """
    Single source of truth for ALL outbound VAPI calls.
    autodial → jessica_gateway → here
    """

    # -------------------------------------------------
    # SAFETY: enforce test number if enabled
    # -------------------------------------------------
    if SAFE_CALL_MODE:
        logger.warning("⚠️ SAFE_CALL_MODE ENABLED — overriding phone number")
        phone_number = SAFE_TEST_NUMBER

    # -------------------------------------------------
    # HARD GUARD: prevent accidental VAPI-owned number usage
    # -------------------------------------------------
    if not VAPI_PHONE_NUMBER_ID:
        raise RuntimeError("❌ VAPI_PHONE_NUMBER_ID is not set")

    logger.info("📞 USING PHONE_NUMBER_ID: %s", VAPI_PHONE_NUMBER_ID)

    # -------------------------------------------------
    # Build payload
    # -------------------------------------------------
    payload = {
        "assistantId": VAPI_ASSISTANT_ID,
        "phoneNumberId": VAPI_PHONE_NUMBER_ID,  # MUST be Twilio-connected
        "customer": {
            "number": phone_number
        },
        "assistantOverrides": {
            # firstMessage is REQUIRED for Jessica to speak first
            "firstMessage": context.pop("__firstMessage", None),
            "context": context
        }
    }

    headers = {
        "Authorization": f"Bearer {get_vapi_private_key()}",
        "Content-Type": "application/json",
    }

    logger.info("🚀 VAPI OUTBOUND PAYLOAD: %s", payload)

    # -------------------------------------------------
    # Send call
    # -------------------------------------------------
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{VAPI_BASE_URL}/call",
            json=payload,
            headers=headers,
        )

    logger.info("📞 VAPI RESPONSE: %s %s", response.status_code, response.text)

    # -------------------------------------------------
    # Fail loudly (no silent fallbacks)
    # -------------------------------------------------
    if response.status_code >= 300:
        raise RuntimeError(
            f"❌ VAPI call failed ({response.status_code}): {response.text}"
        )

    return response.json()