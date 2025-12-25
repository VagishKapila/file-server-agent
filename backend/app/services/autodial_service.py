# backend/app/services/autodial_service.py

import logging
from . import call_engine  # ✅ REQUIRED

logger = logging.getLogger("autodial")

async def trigger_call(*args, **kwargs):
    logger.warning(
        "⚠️ autodial_service.trigger_call() is deprecated. "
        "Calls must go through /autodial/start only."
    )
    return False

TEST_NUMBER_E164 = "+14084106151"  # 🔒 HARD SAFETY LOCK

def run_vendor_autodial_campaign(
    vendors,
    project_address: str,
    trade: str,
    max_confirmed: int = 3,
):
    """
    Uses existing call_engine + safe_call stack.
    Forces all calls to TEST_NUMBER_E164.
    """

    confirmed = 0
    results = []

    for idx, vendor in enumerate(vendors):
        if confirmed >= max_confirmed:
            break

        # 🔐 FORCE SAFE NUMBER
        vendor["phone_e164"] = TEST_NUMBER_E164

        outcome = call_engine.place_call(
            phone_e164=TEST_NUMBER_E164,
            vendor_name=vendor["name"],
            trade=trade,
            project_address=project_address,
        )

        results.append({
            "vendor_id": vendor.get("id"),
            "outcome": outcome,
        })

        if outcome == "answered_human":
            confirmed += 1

    return {
        "confirmed": confirmed,
        "total_called": len(results),
        "results": results,
    }