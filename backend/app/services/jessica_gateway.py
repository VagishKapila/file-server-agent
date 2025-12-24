from backend.app.services.vapi_client import start_call
from typing import List, Union, Optional


async def start_jessica_call(
    phone_number: str,
    vendor: dict,
    project_address: str,
    city: str,
    trades: Union[str, List[str]],
    project_request_id: int,
    callback_phone: str,
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
    # Normalize trades
    # -------------------------------------------------
    if isinstance(trades, str):
        trades = [trades]

    trades = [t for t in trades if t]

    primary_trade = inferred_primary_trade or (trades[0] if trades else "general")
    multiple_trades = len(trades) > 1

    # -------------------------------------------------
    # Spoken opening script (FIX 1)
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
    # Build context sent to VAPI (FIX 2)
    # -------------------------------------------------
    context = {
        "__firstMessage": opening_script,

        # Project identifiers
        "project_request_id": project_request_id,

        # Vendor info
        "vendor": {
            "name": vendor.get("name"),
            "phone": phone_number,
            "email": vendor.get("email"),
        },

        # Project info
        "project_address": project_address,
        "city": city,

        # Trade logic
        "trades": trades,
        "primary_trade": primary_trade,
        "multiple_trades": multiple_trades,

        # Callback
        "callback_phone": callback_phone,

        # Spoken prompts
        "opening_script": opening_script,
        "email_offer_script": email_offer_script,

        # 🔥 HARD FLOW CONTROL (email capture + repeat-back)
        "context_flow": {
            "after_positive_interest": (
                "Great. Before I send anything, what is the best email address "
                "to send the drawings and photos to?"
            ),
            "email_confirmation": (
                "Just to confirm, I heard {email}. Is that correct?"
            ),
        },

        # Soft guidance
        "conversation_guidance": {
            "positive_interest_phrases": [
                "yes",
                "yes open",
                "sure",
                "yeah",
                "yep",
                "we are",
                "we're open",
                "available",
                "interested",
                "possibly",
                "send it",
                "email it",
                "that works",
            ],
            "if_multiple_trades": (
                "Confirm which trade they perform before discussing scope."
            ),
            "if_single_trade": (
                "Proceed directly discussing that trade."
            ),
            "next_step_after_interest": (
                "Force email capture and confirmation before ending the call."
            ),
        },
    }

    # -------------------------------------------------
    # Debug visibility
    # -------------------------------------------------
    print(
        "☎️ STARTING JESSICA CALL",
        {
            "phone": phone_number,
            "project_address": project_address,
            "city": city,
            "primary_trade": primary_trade,
            "trades": trades,
            "project_request_id": project_request_id,
        }
    )

    print("☎️ FINAL DESTINATION NUMBER (PRE-VAPI):", phone_number)
    # -------------------------------------------------
    # Send to VAPI
    # -------------------------------------------------
    return await start_call(phone_number, context)