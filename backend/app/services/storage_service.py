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

_s3_client = None


def _get_s3_client():
    global _s3_client

    if _s3_client:
        return _s3_client

    if not all([R2_ENDPOINT, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET]):
        raise RuntimeError("R2 environment variables are not fully set")

    _s3_client = boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )

    return _s3_client


# --------------------------------------------------
# UPLOAD
# --------------------------------------------------
def upload_bytes(
    *,
    data: bytes,
    key: str,
    content_type: str = "application/octet-stream",
) -> Tuple[str, int]:
    s3 = _get_s3_client()

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
    s3 = _get_s3_client()

    obj = s3.get_object(
        Bucket=R2_BUCKET,
        Key=key,
    )
    return obj["Body"].read()