from __future__ import annotations

from datetime import datetime

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import Payment, PaymentStatus, RegistrationStatus
from ..services.square import verify_signature


webhooks_bp = Blueprint("webhooks", __name__)


def _parse_square_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@webhooks_bp.route("/webhooks/square", methods=["POST"])
def square_webhook():
    signature = request.headers.get("x-square-signature")
    body = request.get_data(as_text=True)

    if not verify_signature(request.url, body, signature):
        current_app.logger.warning("Invalid Square webhook signature.")
        return ("", 403)

    event = request.get_json(silent=True) or {}
    event_type = event.get("type", "")

    if not event_type.startswith("payment."):
        return jsonify({"status": "ignored"})

    payment_data = event.get("data", {}).get("object", {}).get("payment", {})
    square_payment_id = payment_data.get("id")
    if not square_payment_id:
        return jsonify({"status": "ignored"})

    status = (payment_data.get("status") or "").lower()
    payments = Payment.query.filter_by(square_payment_id=square_payment_id).all()

    if not payments:
        current_app.logger.info("Webhook for unknown payment %s", square_payment_id)
        return jsonify({"status": "unknown"})

    paid_at = _parse_square_time(payment_data.get("updated_at"))

    status_mapping = {
        "completed": PaymentStatus.COMPLETED,
        "approved": PaymentStatus.COMPLETED,
        "failed": PaymentStatus.FAILED,
        "canceled": PaymentStatus.FAILED,
        "refunded": PaymentStatus.REFUNDED,
    }
    payment_status = status_mapping.get(status, PaymentStatus.INITIATED)

    for payment in payments:
        payment.status = payment_status
        payment.paid_at = paid_at or payment.paid_at
        payment.raw_payload = payment_data

        registration = payment.registration
        if payment_status == PaymentStatus.COMPLETED:
            registration.status = RegistrationStatus.PAID
        elif payment_status in {PaymentStatus.FAILED, PaymentStatus.REFUNDED}:
            registration.status = RegistrationStatus.CANCELLED

    db.session.commit()
    return jsonify({"status": "ok"})

