from typing import List, Dict, Literal
import time

CallOutcome = Literal["answered_human", "voicemail", "no_answer"]

def simulate_call(vendor: Dict) -> CallOutcome:
    """
    TEMPORARY stub.
    Later this will:
      - dial with Telnyx/Twilio
      - use AMD (answering machine detection)
      - trigger Jessica's live script.
    For now we just pretend we called them.
    """
    name = vendor.get("name", "Unknown Vendor")
    phone = vendor.get("phone") or vendor.get("phone_number", "N/A")

    print(f"📞 [SIM] Calling {name} at {phone}...")

    # TODO: replace this with real provider logic + webhook callbacks
    # For now, just alternate outcomes for demo:
    #   1st: answered_human, 2nd: voicemail, 3rd: no_answer, etc.
    idx = vendor.get("_index", 0)
    if idx % 3 == 0:
        outcome: CallOutcome = "answered_human"
    elif idx % 3 == 1:
        outcome = "voicemail"
    else:
        outcome = "no_answer"

    # tiny simulated delay
    time.sleep(0.2)

    print(f"   ➜ Outcome for {name}: {outcome}")
    return outcome


def leave_voicemail(vendor: Dict, script: str) -> None:
    """
    TEMPORARY stub.
    In real integration we will:
      - play TTS or prerecorded audio
      - then hang up.
    """
    name = vendor.get("name", "Unknown Vendor")
    print(f"📼 [SIM] Leaving voicemail for {name}:")
    print(f"    \"{script}\"")
    # Real provider code would go here.


def run_autodial_campaign(
    vendors: List[Dict],
    project_address: str,
    trade: str,
    max_confirmed: int = 3,
) -> Dict:
    """
    Core engine:
      - Walk vendors in order
      - Stop once max_confirmed is reached
      - Leave voicemail when voicemail detected
      - Never spam: each vendor called at most once per campaign.
    Returns a summary dict.
    """

    print(f"🚀 Starting autodial campaign for trade '{trade}' at '{project_address}'")
    confirmed_count = 0
    call_log: List[Dict] = []

    # Simple script; we can refine this later
    voicemail_script = (
        f"Hi, this is Jessica calling on behalf of a GC with a project near "
        f"{project_address}. We are looking for {trade} bids. "
        f"If you are interested, please text or call back this number and we "
        f"will send full plans and scope. Thank you."
    )

    for idx, vendor in enumerate(vendors):
        if confirmed_count >= max_confirmed:
            print("✅ Reached max confirmed bids, stopping further calls.")
            break

        # attach index for simulate_call rotation
        vendor["_index"] = idx

        outcome = simulate_call(vendor)

        if outcome == "answered_human":
            # For now, assume every human answer is a confirmed bidder.
            # Later: hook in real conversation logic + classification.
            confirmed = True
            confirmed_count += 1

            call_log.append(
                {
                    "vendor": vendor,
                    "outcome": "answered_human",
                    "confirmed_bid": confirmed,
                }
            )

        elif outcome == "voicemail":
            # NEW: leave voicemail instead of hanging up
            leave_voicemail(vendor, voicemail_script)
            call_log.append(
                {
                    "vendor": vendor,
                    "outcome": "voicemail_left",
                    "confirmed_bid": False,
                }
            )

        else:
            # no_answer
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

    print("📊 Autodial summary:", summary)
    return summary
