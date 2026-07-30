"""Webhook sender — notifies th2agent when RAG indexation completes.

Signs each request with HMAC-SHA256 so the receiver can verify authenticity.
Retries with exponential backoff on transient failures.
"""

import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

import httpx

from th2rag.config import settings
from th2rag.utils.logger import setup_logger

logger = setup_logger(__name__)

WEBHOOK_EVENT_INDEXATION_COMPLETED = "indexation.completed"


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 hex digest of the payload using the given secret."""
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()
    return f"sha256={signature}"


def build_webhook_payload(
    knowledge_id: int,
    status: str,
    processing: dict | None = None,
) -> dict[str, Any]:
    """Build the standardised webhook payload dict."""
    return {
        "event": WEBHOOK_EVENT_INDEXATION_COMPLETED,
        "knowledge_id": str(knowledge_id),
        "status": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "processing": processing,
    }


async def send_webhook(
    callback_url: str,
    payload: dict[str, Any],
    *,
    secret: str | None = None,
    timeout_seconds: int | None = None,
    max_retries: int | None = None,
) -> bool:
    """Deliver a signed webhook payload to *callback_url* with exponential back-off.

    Returns True if the delivery succeeded (2xx), False otherwise.
    """
    secret = secret or settings.webhook_secret
    timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.webhook_timeout_seconds
    max_retries = max_retries if max_retries is not None else settings.webhook_max_retries

    payload_bytes = json.dumps(payload, default=str).encode("utf-8")

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-Webhook-Event": WEBHOOK_EVENT_INDEXATION_COMPLETED,
    }

    if secret:
        headers["X-Webhook-Signature"] = _sign_payload(payload_bytes, secret)

    base_delay = 2  # seconds

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                f"[WEBHOOK] Attempt {attempt}/{max_retries} — "
                f"POST {callback_url} (knowledge_id={payload.get('knowledge_id')})"
            )
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                response = await client.post(
                    callback_url,
                    content=payload_bytes,
                    headers=headers,
                )

            if 200 <= response.status_code < 300:
                logger.info(
                    f"[WEBHOOK] Delivered successfully — "
                    f"status={response.status_code}, "
                    f"knowledge_id={payload.get('knowledge_id')}"
                )
                return True

            logger.warning(
                f"[WEBHOOK] Non-2xx response — "
                f"status={response.status_code}, "
                f"body={response.text[:200]}, "
                f"attempt={attempt}/{max_retries}"
            )

        except httpx.TimeoutException:
            logger.warning(
                f"[WEBHOOK] Timeout after {timeout_seconds}s — "
                f"attempt={attempt}/{max_retries}"
            )
        except httpx.RequestError as exc:
            logger.warning(
                f"[WEBHOOK] Request error — {exc!r}, "
                f"attempt={attempt}/{max_retries}"
            )

        # Exponential back-off (2s, 4s, ...) — skip delay after the last attempt
        if attempt < max_retries:
            delay = base_delay * (2 ** (attempt - 1))
            logger.info(f"[WEBHOOK] Retrying in {delay}s...")
            await asyncio.sleep(delay)

    logger.error(
        f"[WEBHOOK] All {max_retries} attempts failed for {callback_url} "
        f"(knowledge_id={payload.get('knowledge_id')})"
    )
    return False
