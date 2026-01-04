# EOF: backend/app/utils/call_guard.py

import os
from typing import Optional

# === ENV FLAGS ===
BETA_MODE = os.getenv("BETA_MODE", "true").lower() == "true"

# Primary beta test phone (Vagish)
BETA_TEST_NUMBER = os.getenv(
    "BETA_TEST_NUMBER",
    "+14084106151"
).strip()


def enforce_test_call(real_vendor_phone: Optional[str]) -> str:
    """
    SINGLE routing decision for outbound calls.

    - If BETA_MODE = true → ALWAYS call beta test number
    - If BETA_MODE = false → call real vendor phone
    """

    if BETA_MODE:
        if not BETA_TEST_NUMBER:
            raise ValueError("BETA_MODE enabled but BETA_TEST_NUMBER not set")
        return BETA_TEST_NUMBER

    if not real_vendor_phone:
        raise ValueError("Missing vendor phone while BETA_MODE=false")

    return real_vendor_phone