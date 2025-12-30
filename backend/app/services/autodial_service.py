import logging
import json
from . import call_engine  # ✅ REQUIRED

logger = logging.getLogger("autodial")

# -----------------------------------------------------------------------------
# DEPRECATED ENTRYPOINT (DO NOT USE)
# -----------------------------------------------------------------------------
async def trigger_call(*args, **kwargs):
    logger.warning(
        "⚠️ autodial_service.trigger_call() is deprecated. "
        "Calls must go through /autodial/start only."
    )
    return False


# -----------------------------------------------------------------------------
# 🔒 HARD SAFETY LOCK — DO NOT REMOVE
# -----------------------------------------------------------------------------
TEST_NUMBER_E164 = "+14084106151"


# -----------------------------------------------------------------------------
# LEGACY / SAFE CALL ENGINE PATH (DO NOT TOUCH)
# This path does NOT use Retell webhooks, attachments, or metadata
# -----------------------------------------------------------------------------
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
            vendor_name=vendor.get("name"),
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


# -----------------------------------------------------------------------------
# 🔑 RETELL AUTODIAL PATH (PRODUCTION)
# -----------------------------------------------------------------------------
def place_retell_call(
    *,
    retell_client,
    agent_id: str,
    from_number: str,
    to_number: str,
    request_form
):
    """
    Places a Retell call and GUARANTEES metadata survives
    so webhooks can resolve VendorCall, attachments, and project.
    """

    # -------------------------------------------------------------------------
    # 🔑 CRITICAL FIX:
    # Always pass through frontend-provided retell_metadata
    # Never overwrite it
    # -------------------------------------------------------------------------
    raw_metadata = request_form.get("retell_metadata")

    try:
        retell_metadata = json.loads(raw_metadata) if raw_metadata else {}
    except Exception:
        logger.exception("❌ Failed to parse retell_metadata")
        retell_metadata = {}

    logger.info(
        "📞 RETELL CREATE | to=%s metadata_keys=%s",
        to_number,
        list(retell_metadata.keys())
    )

    # -------------------------------------------------------------------------
    # Retell call creation (SAFE)
    # -------------------------------------------------------------------------
    response = retell_client.create_call(
        override_agent_id=agent_id,
        from_number=from_number,
        to_number=to_number,
        metadata=retell_metadata  # ✅ DO NOT OVERRIDE
    )

    return response