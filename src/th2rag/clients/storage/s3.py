import io
import os
from datetime import timezone, datetime
from urllib.parse import urlparse

import boto3
from th2rag.config import settings

endpoint_url = settings.s3_endpoint

s3_client = boto3.client(
    "s3",
    aws_access_key_id=settings.s3_access_key,
    aws_secret_access_key=settings.s3_access_key_secret,
    region_name=settings.s3_region,
    endpoint_url=settings.s3_endpoint,  # Custom endpoint for Scaleway's S3 service
)


def upload_file_to_s3(
    file_bytes: bytes, file_name: str, doc_id: int, bucket_name: str = settings.s3_bucket_name
) -> str:
    """
    Uploads file bytes to S3 and returns the URL of the uploaded file.

    :param file_bytes: The file content in bytes.
    :param file_name: The key name to be used for the file in the bucket.
    :param doc_id: The document ID to use as folder prefix in S3.
    :param bucket_name: The S3 bucket name.
    :return: The URL of the uploaded file.
    :raises Exception: If the upload fails.
    """
    try:
        now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base, ext = os.path.splitext(file_name)
        unique_key = f"{doc_id}/{base}_{now}{ext}"
        file_obj = io.BytesIO(file_bytes)
        file_obj.seek(0)

        s3_client.upload_fileobj(
            Fileobj=file_obj,
            Bucket=bucket_name,
            Key=unique_key,
        )

        return f"{endpoint_url}/{bucket_name}/{unique_key}"

    except Exception as e:
        raise RuntimeError(
            f"Failed to upload file '{file_name}'"
        ) from e



def download_file_from_s3(url: str) -> bytes:
    """
    Downloads file bytes from S3 given the full URL and returns them.

    :param url: The full S3 URL.
    :return: The file content in bytes.
    :raises Exception: If the download fails.
    """
    try:
        parsed_url = urlparse(url)

        path_parts = parsed_url.path.lstrip("/").split("/")
        if len(path_parts) < 2:
            raise Exception("URL path is not valid. It must include bucket and file key.")
        bucket = path_parts[0]
        file_key = "/".join(path_parts[1:])

        file_obj = io.BytesIO()
        s3_client.download_fileobj(bucket, file_key, file_obj)
        file_obj.seek(0)
        return file_obj.read()
    except Exception as e:
        raise Exception(f"Failed to download file from URL '{url}': {e}")


def delete_file_from_s3(url: str) -> None:
    """
    Deletes an object from S3 given its full URL.
    """
    parsed = urlparse(url)
    # path is "/bucket/key…"
    parts = parsed.path.lstrip("/").split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URL: {url}")
    bucket, key = parts
    try:
        s3_client.delete_object(Bucket=bucket, Key=key)
    except Exception as e:
        raise RuntimeError(f"Failed to delete S3 object {bucket}/{key}: {e}")
