import os
import logging
import requests
from typing import Optional

logger = logging.getLogger("r2-download")

# REQUIRED
# Example:
# https://<account>.r2.cloudflarestorage.com
R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")


def download_r2_object(r2_path: str) -> Optional[bytes]:
    """
    Download file bytes from Cloudflare R2 using a public endpoint.

    Supports:
      r2://bucket/key

    Returns:
      bytes | None
    """

    if not r2_path.startswith("r2://"):
        logger.error("Invalid R2 path: %s", r2_path)
        return None

    if not R2_PUBLIC_BASE:
        logger.error("R2_PUBLIC_BASE not set")
        return None

    try:
        # r2://bucket/key → key only
        _, rest = r2_path.split("r2://", 1)
        _, key = rest.split("/", 1)

        url = f"{R2_PUBLIC_BASE}/{key}"
    except ValueError:
        logger.error("Malformed R2 path: %s", r2_path)
        return None

    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.error("Failed to download R2 object %s: %s", url, e)
        return None
