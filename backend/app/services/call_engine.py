from typing import List, Dict, Literal
import time

# ==============================
# SAFETY + TEST CONFIG
# ==============================

# 🔒 HARD SAFETY GATE — ONLY YOUR NUMBER WILL EVER BE CALLED
TEST_NUMBER_E164 = "+14084106151"

CallOutcome = Literal["answered_human", "voicemail", "no_answer"]

# ==============================
# CHANNEL RESOLUTION
# ==============================

def resolve_call_channel(vendor: Dict) -> str:
    """
    Decide how to contact vendor.
    PSTN = normal phone call
    WhatsApp = future international / WhatsApp flow
    """
    if vendor.get("supports_whatsapp"):
        return "whatsapp"
    return "pstn"


# ==============================
# SIMULATED CALL (STUB)
# ==============================

def simulate_call(vendor: Dict) -> CallOutcome:
    """
    TEMPORARY stub.
    This will be replaced with Retell live calling.
    """

    name = vendor.get("name", "Unknown Vendor")
    phone = vendor.get("phone_e164", "N/A")
    channel = resolve_call_channel(vendor)

    print(f"📞 [SIM:{channel.upper()}] Calling {name} at {phone}...")

    idx = vendor.get("_index", 0)

    if idx % 3 == 0:
        outcome: CallOutcome = "answered_human"
    elif idx % 3 == 1:
        outcome = "voicemail"
    else:
        outcome = "no_answer"

    time.sleep(0.2)
    print(f"   ➜ Outcome for {name}: {outcome}")
    return outcome


def leave_voicemail(vendor: Dict, script: str) -> None:
    """
    TEMPORARY stub.
    """
    name = vendor.get("name", "Unknown Vendor")
    print(f"📼 [SIM] Leaving voicemail for {name}:")
    print(f'    "{script}"')


# ==============================
# CORE AUTODIAL ENGINE
# ==============================

def run_autodial_campaign(
    vendors: List[Dict],
    project_address: str,
    trade: str,
    max_confirmed: int = 3,
) -> Dict:
    """
    Core autodial logic:
    - Vendors are walked in order
    - Each vendor called once
    - Stop after max_confirmed bids
    - Voicemail left when detected
    - ALL calls forced to TEST_NUMBER_E164
    """

    print(
        f"🚀 Starting autodial campaign | Trade: {trade} | Address: {project_address}"
    )

    confirmed_count = 0
    call_log: List[Dict] = []

    voicemail_script = (
        f"Hi, this is Jessica calling on behalf of a GC with a project near "
        f"{project_address}. We are looking for {trade} bids. "
        f"If you are interested, please text or call back this number and we "
        f"will send full plans and scope. Thank you."
    )

    for idx, vendor in enumerate(vendors):
        if confirmed_count >= max_confirmed:
            print("✅ Max confirmed bids reached. Stopping calls.")
            break

        # 🔐 SAFETY OVERRIDE — DO NOT REMOVE
        vendor["phone_e164"] = TEST_NUMBER_E164

        vendor["_index"] = idx
        outcome = simulate_call(vendor)

        if outcome == "answered_human":
            confirmed_count += 1
            call_log.append(
                {
                    "vendor": vendor,
                    "outcome": "answered_human",
                    "confirmed_bid": True,
                }
            )

        elif outcome == "voicemail":
            leave_voicemail(vendor, voicemail_script)
            call_log.append(
                {
                    "vendor": vendor,
                    "outcome": "voicemail_left",
                    "confirmed_bid": False,
                }
            )

        else:
            call_log.append(
                {
                    "vendor": vendor,
                    "outcome": "no_answer",
                    "confirmed_bid": False,
                }
            )

    summary = {
        "total_vendors": len(vendors),
        "calls_made": len(call_log),
        "confirmed_bids": confirmed_count,
        "max_confirmed": max_confirmed,
        "log": call_log,
    }

    print("📊 AUTODIAL SUMMARY")
    print(summary)
    return summary


# ==============================
# LOCAL TEST RUN
# ==============================

if __name__ == "__main__":
    test_vendors = [
        {
            "name": "Manual Test Plumbing",
            "trade": "plumbing",
            "phone_e164": "+14084106151",
            "supports_whatsapp": False,
        },
        {
            "name": "Alpha Plumbing",
            "trade": "plumbing",
            "phone_e164": "+919999999999",
            "supports_whatsapp": True,
        },
    ]

    run_autodial_campaign(
        vendors=test_vendors,
        project_address="123 Test Street, San Jose CA",
        trade="Plumbing",
        max_confirmed=2,
    )