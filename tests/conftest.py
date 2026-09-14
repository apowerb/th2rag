"""Settings are validated at import time: give the required ones inert values.

setdefault keeps a real environment intact when one is present.
"""

import os

for name in (
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "DB_PORT",
):
    os.environ.setdefault(name, "5432")

for name in (
    "ALGORITHM",
    "DB_HOST",
    "DB_NAME",
    "DB_PASSWORD",
    "DB_SCHEMA",
    "DB_USER",
    "ENCRYPT_KEY",
    "MISTRAL_API_KEY",
    "S3_ACCESS_KEY",
    "S3_ACCESS_KEY_SECRET",
    "S3_BUCKET_NAME",
    "S3_ENDPOINT",
    "S3_REGION",
):
    os.environ.setdefault(name, "test")
