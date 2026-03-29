# backend/app/external/minio_client.py
"""
MinIO (S3-compatible) file storage client — uses boto3 exclusively.
The minio Python package is NEVER used anywhere in this codebase.
Points boto3 at MinIO via endpoint_url=settings.MINIO_ENDPOINT.
"""

from __future__ import annotations

import io
import logging
from typing import Optional

import boto3
from botocore.exceptions import ClientError, EndpointConnectionError

from app.config import settings

logger = logging.getLogger("trustflow.external.minio_client")


def _get_s3_client():
    """
    Create a boto3 S3 client pointed at the MinIO endpoint.

    Uses MINIO_ENDPOINT as the endpoint_url — swappable to AWS S3
    by simply changing the env vars.
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.MINIO_ENDPOINT,
        aws_access_key_id=settings.MINIO_ACCESS_KEY,
        aws_secret_access_key=settings.MINIO_SECRET_KEY,
        region_name="us-east-1",
    )


def ensure_bucket_exists(bucket: Optional[str] = None) -> None:
    """
    Create the bucket if it doesn't exist yet.

    Called during application startup to ensure the receipt bucket exists.

    Args:
        bucket: Bucket name. Defaults to settings.MINIO_BUCKET.
    """
    bucket = bucket or settings.MINIO_BUCKET
    client = _get_s3_client()
    try:
        client.head_bucket(Bucket=bucket)
        logger.info("Bucket '%s' already exists", bucket)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "")
        if error_code in ("404", "NoSuchBucket"):
            logger.info("Creating bucket '%s'", bucket)
            client.create_bucket(Bucket=bucket)
        else:
            raise


def upload_file(
    bucket: str,
    key: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Upload a file to MinIO via boto3.

    Args:
        bucket: S3 bucket name.
        key: Object key (path within bucket).
        data: File bytes to upload.
        content_type: MIME type of the file.

    Returns:
        The object key for later retrieval.

    Raises:
        ClientError: On S3/MinIO upload failure.
    """
    client = _get_s3_client()
    try:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        logger.info("Uploaded %d bytes to s3://%s/%s", len(data), bucket, key)
        return key
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("Failed to upload to s3://%s/%s: %s", bucket, key, exc)
        raise


def download_file(bucket: str, key: str) -> bytes:
    """
    Download a file from MinIO via boto3.

    Args:
        bucket: S3 bucket name.
        key: Object key to download.

    Returns:
        File bytes.

    Raises:
        ClientError: On S3/MinIO download failure.
    """
    client = _get_s3_client()
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        data = response["Body"].read()
        logger.info("Downloaded %d bytes from s3://%s/%s", len(data), bucket, key)
        return data
    except (ClientError, EndpointConnectionError) as exc:
        logger.error("Failed to download s3://%s/%s: %s", bucket, key, exc)
        raise


def check_health() -> bool:
    """
    Check MinIO connectivity by listing buckets.

    Returns:
        True if MinIO is reachable, False otherwise.
    """
    try:
        client = _get_s3_client()
        client.list_buckets()
        return True
    except Exception as exc:
        logger.warning("MinIO health check failed: %s", exc)
        return False
