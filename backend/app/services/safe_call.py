SAFE_CALL_MODE = True  # 🔒 keep ON while testing

SAFE_TEST_NUMBER = "+14084106151"  # Vagish

def get_safe_number(original_number: str | None) -> str | None:
    """
    Forces all outbound calls to a safe test number during testing.
    """
    if SAFE_CALL_MODE:
        return SAFE_TEST_NUMBER

    return original_number