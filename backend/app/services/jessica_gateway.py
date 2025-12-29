from app.services.vapi_client import start_call
from typing import List, Union, Optional


async def start_jessica_call(
    phone_number: str,
    vendor: dict,
    project_address: str,
    project_request_id: int,

    # ✅ backwards + forwards compatible
    trade: Optional[str] = None,
    trades: Union[str, List[str], None] = None,

    city: Optional[str] = "Unknown",
    callback_phone: Optional[str] = None,
    inferred_primary_trade: Optional[str] = None,
):
    """
    Jessica call gateway.

    Design goals:
    - Always speak full address + city clearly
    - Support single or multiple trades
    - Force email capture with confirmation
    - Keep behavior simple and deterministic
    """

    # -------------------------------------------------
    # Normalize trades (SAFE FIX)
    # -------------------------------------------------
    if trades is None and trade:
        trades = [trade]

    if isinstance(trades, str):
        trades = [trades]

    trades = [t for t in (trades or []) if t]

    primary_trade = inferred_primary_trade or (trades[0] if trades else "general")
    multiple_trades = len(trades) > 1

    # -------------------------------------------------
    # Spoken opening script
    # -------------------------------------------------
    if multiple_trades:
        opening_script = (
            f"Hi, this is Jessica from BAINS Development. "
            f"We have an upcoming project at {project_address} in {city}. "
            f"We're currently reaching out regarding "
            f"{', '.join(trades)} work. "
            "Before we go further, which of these trades do you handle?"
        )
    else:
        opening_script = (
            f"Hi, this is Jessica from BAINS Development. "
            f"We have a {primary_trade} project coming up at "
            f"{project_address} in {city}. "
            "Are you currently taking on new work?"
        )

    email_offer_script = (
        "If you'd like, I can email you the drawings and photos "
        "so you can review the project details."
    )

    # -------------------------------------------------
    # Build VAPI context (UNCHANGED LOGIC)
    # -------------------------------------------------
    context = {
        "__firstMessage": opening_script,

        "project_request_id": project_request_id,

        "vendor": {
            "name": vendor.get("name"),
            "phone": phone_number,
            "email": vendor.get("email"),
        },

        "project_address": project_address,
        "city": city,

        "trades": trades,
        "primary_trade": primary_trade,
        "multiple_trades": multiple_trades,

        "callback_phone": callback_phone,

        "opening_script": opening_script,
        "email_offer_script": email_offer_script,

        "context_flow": {
            "after_positive_interest": (
                "Great. Before I send anything, what is the best email address "
                "to send the drawings and photos to?"
            ),
            "email_confirmation": (
                "Just to confirm, I heard {email}. Is that correct?"
            ),
        },
    }

    # -------------------------------------------------
    # Debug
    # -------------------------------------------------
    print("☎️ STARTING JESSICA CALL", {
        "phone": phone_number,
        "project_request_id": project_request_id,
        "primary_trade": primary_trade,
        "trades": trades,
    })

    # -------------------------------------------------
    # Send to VAPI
    # -------------------------------------------------
    return await start_call(phone_number, context)