import os
import boto3
from botocore.client import Config
from typing import Tuple

# --------------------------------------------------
# R2 CONFIG (S3-compatible)
# --------------------------------------------------
R2_ENDPOINT = os.getenv("R2_ENDPOINT")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET = os.getenv("R2_BUCKET")

if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET]):
    raise RuntimeError("❌ R2 environment variables are not fully set")

# --------------------------------------------------
# S3 CLIENT (Cloudflare R2)
# --------------------------------------------------
s3 = boto3.client(
    "s3",
    endpoint_url=R2_ENDPOINT,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version="s3v4"),
    region_name="auto",
)

# --------------------------------------------------
# UPLOAD
# --------------------------------------------------
def upload_bytes(
    *,
    data: bytes,
    key: str,
    content_type: str = "application/octet-stream",
) -> Tuple[str, int]:
    """
    Upload raw bytes to R2.

    Returns:
        (r2_uri, size_bytes)
    """
    s3.put_object(
        Bucket=R2_BUCKET,
        Key=key,
        Body=data,
        ContentType=content_type,
    )

    return f"r2://{R2_BUCKET}/{key}", len(data)

# --------------------------------------------------
# DOWNLOAD
# --------------------------------------------------
def download_bytes(key: str) -> bytes:
    """
    Download object bytes from R2.
    """
    obj = s3.get_object(
        Bucket=R2_BUCKET,
        Key=key,
    )
    return obj["Body"].read()
