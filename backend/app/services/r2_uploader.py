import os
import boto3
from botocore.client import Config
from typing import Optional


def _get_r2_client():
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        raise RuntimeError("Missing R2 credentials")

    endpoint = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


def upload_file_to_r2(
    *,
    data: bytes,
    r2_key: str,
    content_type: Optional[str] = "application/octet-stream",
) -> str:
    if not data:
        raise ValueError("No data provided for R2 upload")

    R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")
    R2_PUBLIC_BASE = os.getenv("R2_PUBLIC_BASE")

    if not all([R2_BUCKET_NAME, R2_PUBLIC_BASE]):
        raise RuntimeError("Missing R2 bucket config")

    s3 = _get_r2_client()

    s3.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=r2_key,
        Body=data,
        ContentType=content_type,
    )

    return f"{R2_PUBLIC_BASE}/{r2_key}"