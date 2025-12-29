# backend/app/utils/phone_utils.py

import re
from typing import Optional, Dict

US_COUNTRY_CODE = "+1"


def strip_non_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def normalize_phone(phone: Optional[str], default_country: str = "US") -> Optional[str]:
    """
    Normalize phone number to E.164 format.
    Returns None if not callable.
    """
    if not phone:
        return None

    digits = strip_non_digits(phone)

    # US number
    if default_country == "US":
        if len(digits) == 10:
            return f"+1{digits}"
        if len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"

    # India
    if default_country == "IN":
        if len(digits) == 10:
            return f"+91{digits}"
        if digits.startswith("91") and len(digits) == 12:
            return f"+{digits}"

    # Already E.164
    if phone.startswith("+") and len(digits) >= 10:
        return f"+{digits}"

    return None


def is_callable(phone: Optional[str]) -> bool:
    return normalize_phone(phone) is not None


def analyze_phone(phone: Optional[str]) -> Dict:
    """
    Diagnostics for debugging / logging
    """
    normalized = normalize_phone(phone)
    return {
        "raw": phone,
        "normalized": normalized,
        "callable": bool(normalized),
    }