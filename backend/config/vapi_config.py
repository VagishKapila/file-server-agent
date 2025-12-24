import os
from dotenv import load_dotenv
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / "app" / ".env"
load_dotenv(dotenv_path=ENV_PATH, override=True)

# =========================
# VAPI CONFIG (SAFE)
# =========================

VAPI_BASE_URL = "https://api.vapi.ai"

VAPI_ASSISTANT_ID = os.getenv("VAPI_ASSISTANT_ID")
VAPI_PHONE_NUMBER_ID = os.getenv("VAPI_PHONE_NUMBER_ID")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# =========================
# SAFE CALL MODE
# =========================

SAFE_CALL_MODE = False
SAFE_TEST_NUMBER = "+14084106151"

# =========================
# KEY ACCESS (RUNTIME)
# =========================

def get_vapi_private_key() -> str:
    key = os.environ.get("VAPI_PRIVATE_KEY")
    if not key:
        raise RuntimeError("❌ VAPI_PRIVATE_KEY missing from environment")
    return key