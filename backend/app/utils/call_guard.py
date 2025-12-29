import os

# Comma-separated test numbers allowed to receive calls
TEST_CALL_NUMBERS = os.getenv(
    "TEST_CALL_NUMBERS",
    "+14084106151"  # your phone default
).split(",")

TEST_MODE = os.getenv("CALL_TEST_MODE", "true").lower() == "true"


def enforce_test_call(real_vendor_phone: str | None) -> str:
    """
    Enforces test-only calling.
    - If TEST_MODE is ON → always return tester phone
    - If OFF → return real vendor phone
    """

    if TEST_MODE:
        # Always call first test number
        return TEST_CALL_NUMBERS[0].strip()

    if not real_vendor_phone:
        raise ValueError("Missing vendor phone")

    return real_vendor_phone