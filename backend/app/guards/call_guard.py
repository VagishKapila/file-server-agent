# backend/app/guards/call_guard.py
"""
Central outbound call safety guard.

This module ensures NO real vendors are called during testing.
It is the single source of truth for outbound dialing behavior.
"""

from typing import List, Dict
import os

# =========================
# GLOBAL CALL MODE
# =========================
# TEST  -> only test numbers are dialed
# LIVE  -> real vendor numbers are dialed
CALL_MODE = os.getenv("CALL_MODE", "TEST").upper()

# =========================
# TEST NUMBERS (SAFE)
# =========================
TEST_NUMBERS: List[Dict] = [
    {
        "name": "TEST CALL",
        "phone": "+14084106151",  # Vagish cell (safe test target)
    }
]

# =========================
# MAIN GUARD FUNCTION
# =========================
def guard_vendors(vendors: List[Dict]) -> List[Dict]:
    """
    Gatekeeper for ALL outbound calls.
    This function MUST be called before dialing.
    """

    if CALL_MODE != "LIVE":
        print("🛑 CALL GUARD ACTIVE — TEST MODE")
        print("📞 Overriding vendor list with TEST numbers only")
        return TEST_NUMBERS

    print("⚠️ CALL GUARD DISABLED — LIVE MODE")
    return vendors
