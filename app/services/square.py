from __future__ import annotations

import logging
import uuid
from functools import lru_cache

from flask import current_app
from square.client import Client
from square.error import ApiException
from square.webhook.signature import is_valid_signature

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _build_client(access_token: str, environment: str) -> Client:
    return Client(access_token=access_token, environment=environment)


def get_client() -> Client:
    access_token = current_app.config.get("SQUARE_ACCESS_TOKEN")
    environment = current_app.config.get("SQUARE_ENVIRONMENT", "sandbox")
    if not access_token:
        raise RuntimeError("Square access token is not configured.")
    return _build_client(access_token, environment)


def create_payment(
    *,
    amount_cents: int,
    source_id: str,
    location_id: str,
    buyer_email: str | None = None,
    buyer_phone: str | None = None,
    buyer_name: str | None = None,
    verification_token: str | None = None,
    note: str | None = None,
) -> dict:
    client = get_client()
    idempotency_key = str(uuid.uuid4())
    body: dict = {
        "source_id": source_id,
        "idempotency_key": idempotency_key,
        "amount_money": {"amount": amount_cents, "currency": "USD"},
        "location_id": location_id,
        "autocomplete": True,
    }

    if verification_token:
        body["verification_token"] = verification_token
    if buyer_email:
        body["buyer_email_address"] = buyer_email
    if buyer_phone:
        body["buyer_phone_number"] = buyer_phone
    if buyer_name:
        body["note"] = note or f"Checkout for {buyer_name}"
    elif note:
        body["note"] = note

    try:
        result = client.payments.create_payment(body)
    except ApiException as exc:  # pragma: no cover - network call
        logger.exception("Square payment API error: %s", exc)
        raise

    if result.is_success():
        return result.body.get("payment", {})

    logger.error("Square payment failed: %s", result.errors)
    raise RuntimeError(result.errors)


def verify_signature(notification_url: str, body: str, signature: str | None) -> bool:
    signature_key = current_app.config.get("SQUARE_WEBHOOK_SIGNATURE_KEY")
    if not signature_key:
        logger.warning("No Square webhook signature key configured; skipping verification.")
        return True
    if not signature:
        return False
    return is_valid_signature(notification_url, body, signature, signature_key)

