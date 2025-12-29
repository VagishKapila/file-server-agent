import os
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

import requests

logger = logging.getLogger("r2-download")

# Can be either:
# 1) Account endpoint (NO bucket in base):
#    https://<accountid>.r2.cloudflarestorage.com
# 2) Account endpoint + bucket path:
#    https://<accountid>.r2.cloudflarestorage.com/<bucket>
# 3) Custom domain mapped to a bucket root:
#    https://files.yourdomain.com
R2_PUBLIC_BASE = (os.getenv("R2_PUBLIC_BASE") or "").rstrip("/")


def _parse_r2_uri(r2_uri: str) -> Optional[Tuple[str, str]]:
    # r2://bucket/key -> (bucket, key)
    if not r2_uri or not r2_uri.startswith("r2://"):
        return None
    rest = r2_uri[len("r2://"):]
    if "/" not in rest:
        return None
    bucket, key = rest.split("/", 1)
    if not bucket or not key:
        return None
    return bucket, key


def _base_includes_bucket(base: str, bucket: str) -> bool:
    """
    True if base already points at the bucket root.
    Handles:
      - https://bucket.<account>.r2.cloudflarestorage.com
      - https://<account>.r2.cloudflarestorage.com/bucket
    """
    try:
        p = urlparse(base)
        host = (p.netloc or "").lower()
        path = (p.path or "").strip("/")

        if host.startswith(bucket.lower() + "."):
            return True

        if path == bucket or path.endswith("/" + bucket):
            return True

        return False
    except Exception:
        return False


def build_public_url(r2_uri: str) -> Optional[str]:
    if not R2_PUBLIC_BASE:
        logger.error("R2_PUBLIC_BASE not set")
        return None

    parsed = _parse_r2_uri(r2_uri)
    if not parsed:
        logger.error("Invalid R2 URI: %s", r2_uri)
        return None

    bucket, key = parsed

    # If base already includes bucket -> BASE/<key>
    if _base_includes_bucket(R2_PUBLIC_BASE, bucket):
        return f"{R2_PUBLIC_BASE}/{key}"

    # Else -> BASE/<bucket>/<key>
    return f"{R2_PUBLIC_BASE}/{bucket}/{key}"


def download_r2_object(r2_uri: str, timeout_s: int = 60) -> Optional[bytes]:
    url = build_public_url(r2_uri)
    if not url:
        return None

    try:
        resp = requests.get(url, timeout=timeout_s)
        resp.raise_for_status()
        return resp.content
    except Exception as e:
        logger.error("Failed to download R2 object %s: %s", url, e)
        return None
