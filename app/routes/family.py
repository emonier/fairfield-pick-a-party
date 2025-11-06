from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..forms import AddToCartForm, CheckoutForm
from ..models import Party, Payment, PaymentStatus, Registration, RegistrationStatus
from ..services.square import create_payment
from ..extensions import db


FAMILY_ACCESS_KEY = "family_access_granted"
CART_SESSION_KEY = "family_cart"
LAST_ORDER_SESSION_KEY = "family_last_order"

family_bp = Blueprint("family", __name__)


@family_bp.before_app_request
def ensure_session_key() -> None:
    session.setdefault(FAMILY_ACCESS_KEY, False)


def _require_access() -> bool:
    return bool(session.get(FAMILY_ACCESS_KEY))


def _get_cart() -> Dict[str, int]:
    raw = session.setdefault(CART_SESSION_KEY, {})
    cart: Dict[str, int] = {}
    for key, value in raw.items():
        try:
            qty = int(value)
        except (TypeError, ValueError):
            continue
        if qty > 0:
            cart[str(int(key))] = qty
    if cart != raw:
        session[CART_SESSION_KEY] = cart
        session.modified = True
    return cart


def _save_cart(cart: Dict[str, int]) -> None:
    session[CART_SESSION_KEY] = cart
    session.modified = True


def _clear_cart() -> None:
    session[CART_SESSION_KEY] = {}
    session.modified = True


def _cart_items() -> List[Dict[str, Any]]:
    cart = _get_cart()
    if not cart:
        return []
    party_ids = [int(pid) for pid in cart.keys()]
    parties = Party.query.filter(Party.id.in_(party_ids)).all()
    party_lookup = {party.id: party for party in parties}

    items: List[Dict[str, Any]] = []
    changed = False
    for pid, qty in cart.items():
        party = party_lookup.get(int(pid))
        if not party:
            changed = True
            continue
        limited_qty = min(qty, party.max_tickets_per_order)
        if party.spots_remaining:
            limited_qty = min(limited_qty, party.spots_remaining)
        if limited_qty <= 0:
            changed = True
            continue
        if limited_qty != qty:
            cart[pid] = limited_qty
            changed = True
        items.append(
            {
                "party": party,
                "quantity": limited_qty,
                "unit_price_cents": party.price_cents,
                "total_cents": party.price_cents * limited_qty,
            }
        )
    if changed:
        _save_cart(cart)
    items.sort(key=lambda item: item["party"].event_date)
    return items


def _cart_totals(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    subtotal_cents = sum(item["total_cents"] for item in items)
    subtotal = Decimal(subtotal_cents) / Decimal(100)
    total_quantity = sum(item["quantity"] for item in items)
    return {
        "subtotal_cents": subtotal_cents,
        "subtotal": subtotal,
        "total_quantity": total_quantity,
    }


def _parse_square_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _store_last_order(order: Dict[str, Any]) -> None:
    session[LAST_ORDER_SESSION_KEY] = order
    session.modified = True


@family_bp.route("/")
def home():
    if not _require_access():
        return redirect(url_for("family.access"))
    parties = Party.query.order_by(Party.event_date.asc()).all()
    forms: Dict[int, AddToCartForm] = {}
    for party in parties:
        form = AddToCartForm()
        form.party_id.data = str(party.id)
        form.quantity.data = 1 if party.max_tickets_per_order > 0 else 0
        form.quantity.render_kw = {
            "min": 1,
            "max": party.max_tickets_per_order,
            "step": 1,
            "class": "form-control",
        }
        form.quantity.id = f"quantity-{party.id}"
        forms[party.id] = form
    return render_template("family/index.html", parties=parties, forms=forms)


@family_bp.route("/access", methods=["GET", "POST"])
def access():
    error = None
    if request.method == "POST":
        shared_password = request.form.get("shared_password", "").strip()
        expected_password = current_app.config.get("SECURITY_SHARED_PASSWORD")
        if shared_password and shared_password == expected_password:
            session[FAMILY_ACCESS_KEY] = True
            return redirect(url_for("family.home"))
        error = "Incorrect password. Please try again."
    return render_template("family/access.html", error=error)


@family_bp.route("/logout")
def logout_access():
    session[FAMILY_ACCESS_KEY] = False
    return redirect(url_for("family.access"))


@family_bp.route("/cart/add", methods=["POST"])
def add_to_cart():
    if not _require_access():
        return redirect(url_for("family.access"))

    form = AddToCartForm()
    if not form.validate_on_submit():
        flash("Please provide a valid quantity.", "danger")
        return redirect(url_for("family.home"))

    party = Party.query.get_or_404(int(form.party_id.data))
    if party.spots_remaining <= 0:
        flash("This party is currently sold out.", "warning")
        return redirect(url_for("family.home"))

    requested_qty = form.quantity.data or 1
    requested_qty = min(requested_qty, party.max_tickets_per_order)
    if party.spots_remaining:
        requested_qty = min(requested_qty, party.spots_remaining)
    if requested_qty <= 0:
        flash("Unable to add tickets at this time.", "warning")
        return redirect(url_for("family.home"))

    cart = _get_cart()
    current_qty = cart.get(str(party.id), 0)
    new_qty = min(current_qty + requested_qty, party.max_tickets_per_order)
    if party.spots_remaining:
        new_qty = min(new_qty, party.spots_remaining)

    cart[str(party.id)] = new_qty
    _save_cart(cart)
    added = new_qty - current_qty
    if added <= 0:
        flash("This party is already at the maximum quantity in your cart.", "info")
    else:
        flash(f"Added {added} spot(s) for {party.title} to your cart.", "success")
    return redirect(url_for("family.home"))


@family_bp.route("/cart")
def view_cart():
    if not _require_access():
        return redirect(url_for("family.access"))
    items = _cart_items()
    totals = _cart_totals(items)
    return render_template("family/cart.html", items=items, totals=totals)


@family_bp.route("/cart/update/<int:party_id>", methods=["POST"])
def update_cart(party_id: int):
    if not _require_access():
        return redirect(url_for("family.access"))
    cart = _get_cart()
    party = Party.query.get_or_404(party_id)
    try:
        quantity = int(request.form.get("quantity", 1))
    except ValueError:
        quantity = 1

    quantity = max(0, min(quantity, party.max_tickets_per_order))
    if party.spots_remaining:
        quantity = min(quantity, party.spots_remaining)

    if quantity == 0:
        cart.pop(str(party.id), None)
    else:
        cart[str(party.id)] = quantity
    _save_cart(cart)
    flash("Your cart has been updated.", "success")
    return redirect(url_for("family.view_cart"))


@family_bp.route("/cart/remove/<int:party_id>")
def remove_from_cart(party_id: int):
    if not _require_access():
        return redirect(url_for("family.access"))
    cart = _get_cart()
    removed = cart.pop(str(party_id), None)
    _save_cart(cart)
    if removed:
        flash("Item removed from cart.", "info")
    return redirect(url_for("family.view_cart"))


@family_bp.route("/checkout", methods=["GET"])
def checkout():
    if not _require_access():
        return redirect(url_for("family.access"))

    items = _cart_items()
    if not items:
        flash("Your cart is empty. Please add a party first.", "warning")
        return redirect(url_for("family.home"))

    totals = _cart_totals(items)
    form = CheckoutForm()
    square_environment = current_app.config.get("SQUARE_ENVIRONMENT", "sandbox")
    square_application_id = current_app.config.get("SQUARE_APPLICATION_ID")
    square_location_id = current_app.config.get("SQUARE_LOCATION_ID")

    return render_template(
        "family/checkout.html",
        items=items,
        totals=totals,
        form=form,
        square_environment=square_environment,
        square_application_id=square_application_id,
        square_location_id=square_location_id,
    )


@family_bp.route("/api/checkout", methods=["POST"])
def process_checkout():
    if not _require_access():
        return jsonify({"error": "unauthorized"}), 401

    square_access_token = current_app.config.get("SQUARE_ACCESS_TOKEN")
    square_location_id = current_app.config.get("SQUARE_LOCATION_ID")
    if not square_access_token or not square_location_id:
        return jsonify({"error": "Payment processing is not available right now."}), 503

    payload = request.get_json(silent=True) or {}
    source_id = payload.get("sourceId")
    verification_token = payload.get("verificationToken")
    family_name = (payload.get("familyName") or "").strip() or "Anonymous Family"
    family_email = (payload.get("familyEmail") or "").strip()
    family_phone = (payload.get("familyPhone") or "").strip()
    expose_contact = bool(payload.get("exposeContact", True))

    if not source_id:
        return jsonify({"error": "Missing payment token."}), 400
    if not family_email:
        return jsonify({"error": "Email address is required."}), 400

    items = _cart_items()
    if not items:
        return jsonify({"error": "Your cart is empty."}), 400

    totals = _cart_totals(items)
    if totals["subtotal_cents"] <= 0:
        return jsonify({"error": "Unable to process a $0 payment."}), 400

    for item in items:
        party: Party = item["party"]
        if party.spots_remaining and item["quantity"] > party.spots_remaining:
            message = f"{party.title} no longer has enough availability."
            return jsonify({"error": message}), 400

    try:
        payment = create_payment(
            amount_cents=totals["subtotal_cents"],
            source_id=source_id,
            location_id=square_location_id,
            buyer_email=family_email,
            buyer_phone=family_phone,
            buyer_name=family_name,
            verification_token=verification_token,
            note=f"Pick-A-Party checkout for {family_name}",
        )
    except Exception as exc:  # pragma: no cover - network call
        current_app.logger.exception("Square payment failed: %s", exc)
        return jsonify({"error": "Payment could not be completed. Please try again."}), 400

    payment_status = (payment.get("status") or "").lower()
    payment_id = payment.get("id")
    is_paid = payment_status in {"completed", "approved"}

    try:
        order_items: List[Dict[str, Any]] = []
        for item in items:
            party: Party = item["party"]
            registration = Registration(
                party_id=party.id,
                family_name=family_name,
                family_email=family_email,
                family_phone=family_phone,
                quantity=item["quantity"],
                status=RegistrationStatus.PAID if is_paid else RegistrationStatus.PENDING,
                expose_contact_to_host=expose_contact,
            )
            db.session.add(registration)
            db.session.flush()

            payment_record = Payment(
                registration_id=registration.id,
                square_payment_id=payment_id,
                status=PaymentStatus.COMPLETED if is_paid else PaymentStatus.INITIATED,
                amount_cents=item["total_cents"],
                paid_at=_parse_square_time(payment.get("updated_at")),
                raw_payload=payment,
            )
            db.session.add(payment_record)

            order_items.append(
                {
                    "party_title": party.title,
                    "event_date": party.event_date.isoformat(),
                    "quantity": item["quantity"],
                    "host_email": party.host_contact_email,
                    "host_name": party.host_contact_name,
                }
            )

        db.session.commit()
    except Exception:  # pragma: no cover - db failure
        db.session.rollback()
        current_app.logger.exception("Failed to persist checkout data.")
        return (
            jsonify(
                {
                    "error": "We received your payment but could not record the registration. Please contact the school with your receipt.",
                }
            ),
            500,
        )

    _clear_cart()
    _store_last_order(
        {
            "family_name": family_name,
            "family_email": family_email,
            "items": order_items,
            "payment_id": payment_id,
            "amount_cents": totals["subtotal_cents"],
            "status": payment_status,
            "paid": is_paid,
        }
    )
    flash("Thank you! Your payment was processed successfully.", "success")

    return jsonify({"redirect_url": url_for("family.checkout_success")})


@family_bp.route("/checkout/success")
def checkout_success():
    if not _require_access():
        return redirect(url_for("family.access"))
    order = session.get(LAST_ORDER_SESSION_KEY)
    if not order:
        return redirect(url_for("family.home"))

    session.pop(LAST_ORDER_SESSION_KEY, None)
    session.modified = True

    items = []
    for item in order.get("items", []):
        event_date = None
        if iso_date := item.get("event_date"):
            try:
                event_date = datetime.fromisoformat(iso_date)
            except ValueError:
                event_date = None
        items.append({**item, "event_date": event_date})

    total = Decimal(order.get("amount_cents", 0)) / Decimal(100)
    return render_template(
        "family/checkout_success.html",
        order=order,
        items=items,
        total=total,
    )
@family_bp.route("/api/cart/summary")
def cart_summary():
    if not _require_access():
        return jsonify({"error": "unauthorized"}), 401
    items = _cart_items()
    totals = _cart_totals(items)
    response_items = [
        {
            "party_id": item["party"].id,
            "title": item["party"].title,
            "quantity": item["quantity"],
            "unit_price_cents": item["unit_price_cents"],
            "total_cents": item["total_cents"],
        }
        for item in items
    ]
    totals_payload = {
        "subtotal_cents": totals["subtotal_cents"],
        "subtotal": float(totals["subtotal"]),
        "total_quantity": totals["total_quantity"],
    }
    return jsonify({"items": response_items, "totals": totals_payload})

