# backend/app/utils/call_guard.py

import os

TEST_MODE = os.getenv("TEST_MODE", "true").lower() == "true"
TEST_PHONE = os.getenv("TEST_PHONE", "+14084106151")  # your number


def enforce_test_call(vendor_phone: str) -> str:
    """
    During test mode, ALL calls go to test phone.
    """
    if TEST_MODE:
        return TEST_PHONE
    return vendor_phone