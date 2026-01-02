# backend/app/services/autodial_service.py

import logging
from . import call_engine  # ✅ REQUIRED

logger = logging.getLogger("autodial")

TEST_NUMBER_E164 = "+14084106151"  # 🔒 HARD SAFETY LOCK (default)

async def trigger_call(*args, **kwargs):
    logger.warning(
        "⚠️ autodial_service.trigger_call() is deprecated. "
        "Calls must go through /autodial/start only."
    )
    return False


def run_vendor_autodial_campaign(
    vendors,
    project_address: str,
    trade: str,
    max_confirmed: int = 3,
    callback_phone: str | None = None,   # ✅ NEW
):
    """
    Uses existing call_engine + safety stack.

    Behavior:
    - If callback_phone is provided → call THAT number
    - Otherwise → fall back to TEST_NUMBER_E164
    - NEVER calls real vendor numbers (safe)
    """

    confirmed = 0
    results = []

    # 🔐 Decide final dial number (THIS WAS MISSING)
    dial_number = callback_phone or TEST_NUMBER_E164

    logger.info("📞 AUTODIAL TARGET NUMBER = %s", dial_number)

    for idx, vendor in enumerate(vendors):
        if confirmed >= max_confirmed:
            break

        # 🔐 FORCE SAFE NUMBER (vendor phone is ignored)
        vendor["phone_e164"] = dial_number

        outcome = call_engine.place_call(
            phone_e164=dial_number,
            vendor_name=vendor.get("name", "Test Vendor"),
            trade=trade,
            project_address=project_address,
        )

        results.append({
            "vendor_id": vendor.get("id"),
            "dialed": dial_number,
            "outcome": outcome,
        })

        if outcome == "answered_human":
            confirmed += 1

    return {
        "confirmed": confirmed,
        "total_called": len(results),
        "dialed_number": dial_number,
        "results": results,
    }