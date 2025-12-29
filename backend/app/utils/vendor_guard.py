# backend/app/utils/vendor_guard.py

from typing import Dict, Optional
from .phone_utils import normalize_phone

JUNK_PATTERNS = [
    "call us",
    "contact",
    "toll free",
    "phone:",
    "tel:",
]


def is_junk_phone(phone: Optional[str]) -> bool:
    if not phone:
        return True

    p = phone.lower()
    if any(j in p for j in JUNK_PATTERNS):
        return True

    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 10:
        return True

    return False


def clean_vendor_result(raw: Dict) -> Optional[Dict]:
    """
    Takes raw Google/Yelp vendor dict
    Returns cleaned dict OR None if junk
    """

    phone = raw.get("phone")
    if is_junk_phone(phone):
        return None

    normalized = normalize_phone(phone)

    if not normalized:
        return None

    return {
        "name": raw.get("name"),
        "trade": raw.get("trade"),
        "phone": normalized,
        "email": raw.get("email"),
        "source": raw.get("source", "google"),
    }