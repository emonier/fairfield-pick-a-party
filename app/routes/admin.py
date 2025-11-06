from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from ..extensions import db
from ..forms import AdminLoginForm, PartyForm, RegistrationImportForm
from ..models import (
    AdminUser,
    Party,
    Payment,
    PaymentStatus,
    PriceUnit,
    Registration,
    RegistrationStatus,
)


admin_bp = Blueprint("admin", __name__, template_folder="../templates/admin")


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = AdminLoginForm()
    if form.validate_on_submit():
        admin = AdminUser.query.filter_by(email=form.email.data.lower()).first()
        if admin and admin.check_password(form.password.data):
            login_user(admin)
            flash("Welcome back!", "success")
            next_url = request.args.get("next")
            return redirect(next_url or url_for("admin.dashboard"))
        flash("Invalid credentials", "danger")

    return render_template("admin/login.html", form=form)


@admin_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@login_required
def dashboard():
    party_count = Party.query.count()

    paid_registrations = (
        db.session.query(func.coalesce(func.sum(Registration.quantity), 0))
        .filter(Registration.status == RegistrationStatus.PAID)
        .scalar()
        or 0
    )

    pending_registrations = (
        db.session.query(func.count(Registration.id))
        .filter(Registration.status == RegistrationStatus.PENDING)
        .scalar()
        or 0
    )

    total_revenue_cents = (
        db.session.query(func.coalesce(func.sum(Payment.amount_cents), 0))
        .filter(Payment.status == PaymentStatus.COMPLETED)
        .scalar()
        or 0
    )
    total_revenue = total_revenue_cents / 100

    parties = Party.query.order_by(Party.event_date.asc()).all()
    party_summaries = []
    for party in parties:
        confirmed = sum(
            reg.quantity for reg in party.registrations if reg.status == RegistrationStatus.PAID
        )
        revenue_cents = sum(
            payment.amount_cents
            for reg in party.registrations
            for payment in reg.payments
            if payment.status == PaymentStatus.COMPLETED
        )
        summary = {
            "party": party,
            "remaining": party.spots_remaining,
            "confirmed": confirmed,
            "revenue": revenue_cents / 100,
        }
        party_summaries.append(summary)

    recent_payments = (
        Payment.query.filter(Payment.status == PaymentStatus.COMPLETED)
        .order_by(Payment.paid_at.desc().nullslast())
        .limit(5)
        .all()
    )

    return render_template(
        "admin/dashboard.html",
        party_count=party_count,
        paid_registrations=paid_registrations,
        pending_registrations=pending_registrations,
        total_revenue=total_revenue,
        party_summaries=party_summaries,
        recent_payments=recent_payments,
    )


@admin_bp.route("/parties", methods=["GET", "POST"])
@login_required
def manage_parties():
    form = PartyForm()
    if form.validate_on_submit():
        party = Party(
            title=form.title.data,
            description=form.description.data,
            event_date=form.event_date.data,
            price_cents=form.price_cents.data,
            price_unit=PriceUnit(form.price_unit.data),
            total_spots=form.total_spots.data,
            max_tickets_per_order=form.max_tickets_per_order.data,
            host_contact_name=form.host_contact_name.data,
            host_contact_email=form.host_contact_email.data,
            host_contact_phone=form.host_contact_phone.data,
        )
        db.session.add(party)
        db.session.commit()
        flash("Party created successfully", "success")
        return redirect(url_for("admin.manage_parties"))

    parties = Party.query.order_by(Party.event_date.asc()).all()
    return render_template("admin/parties.html", form=form, parties=parties)


@admin_bp.route("/parties/<int:party_id>")
@login_required
def view_party(party_id: int):
    party = Party.query.get_or_404(party_id)
    registrations = (
        Registration.query.filter_by(party_id=party.id)
        .order_by(Registration.created_at.desc())
        .all()
    )

    paid = sum(reg.quantity for reg in registrations if reg.status == RegistrationStatus.PAID)
    pending = sum(
        reg.quantity for reg in registrations if reg.status == RegistrationStatus.PENDING
    )
    revenue_cents = sum(
        payment.amount_cents
        for reg in registrations
        for payment in reg.payments
        if payment.status == PaymentStatus.COMPLETED
    )

    import_form = RegistrationImportForm()
    import_form.party_id.choices = [(party.id, party.title)]
    import_form.party_id.data = party.id

    return render_template(
        "admin/party_detail.html",
        party=party,
        registrations=registrations,
        paid=paid,
        pending=pending,
        revenue=revenue_cents / 100,
        import_form=import_form,
    )


@admin_bp.route("/parties/<int:party_id>/edit", methods=["GET", "POST"])
@login_required
def edit_party(party_id: int):
    party = Party.query.get_or_404(party_id)
    form = PartyForm(obj=party)
    if request.method == "GET":
        form.price_unit.data = party.price_unit.value
    if form.validate_on_submit():
        party.title = form.title.data
        party.description = form.description.data
        party.event_date = form.event_date.data
        party.price_cents = form.price_cents.data
        party.price_unit = PriceUnit(form.price_unit.data)
        party.total_spots = form.total_spots.data
        party.max_tickets_per_order = form.max_tickets_per_order.data
        party.host_contact_name = form.host_contact_name.data
        party.host_contact_email = form.host_contact_email.data
        party.host_contact_phone = form.host_contact_phone.data
        db.session.commit()
        flash("Party updated successfully.", "success")
        return redirect(url_for("admin.view_party", party_id=party.id))

    return render_template("admin/edit_party.html", form=form, party=party)


@admin_bp.route("/parties/<int:party_id>/delete", methods=["POST"])
@login_required
def delete_party(party_id: int):
    party = Party.query.get_or_404(party_id)
    db.session.delete(party)
    db.session.commit()
    flash("Party deleted.", "info")
    return redirect(url_for("admin.manage_parties"))


@admin_bp.route("/registrations")
@login_required
def registrations():
    registrations = (
        Registration.query.order_by(Registration.created_at.desc())
        .limit(200)
        .all()
    )
    parties = Party.query.order_by(Party.title.asc()).all()
    import_form = RegistrationImportForm()
    import_form.party_id.choices = [(party.id, party.title) for party in parties]
    return render_template(
        "admin/registrations.html",
        registrations=registrations,
        import_form=import_form,
    )


@admin_bp.route("/registrations/export")
@login_required
def export_registrations() -> Response:
    registrations = (
        Registration.query.join(Party)
        .add_columns(Party.title.label("party_title"))
        .order_by(Registration.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Party",
            "Family Name",
            "Email",
            "Phone",
            "Quantity",
            "Status",
            "Expose Contact",
            "Created At",
        ]
    )
    for registration, party_title in registrations:
        writer.writerow(
            [
                party_title,
                registration.family_name,
                registration.family_email,
                registration.family_phone,
                registration.quantity,
                registration.status.value,
                "yes" if registration.expose_contact_to_host else "no",
                registration.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )

    csv_data = output.getvalue()
    output.close()
    headers = {
        "Content-Disposition": "attachment; filename=registrations.csv",
        "Content-Type": "text/csv",
    }
    return Response(csv_data, headers=headers)


@admin_bp.route("/registrations/import", methods=["POST"])
@login_required
def import_registrations():
    form = RegistrationImportForm()
    parties = Party.query.order_by(Party.title.asc()).all()
    form.party_id.choices = [(party.id, party.title) for party in parties]

    if not form.validate_on_submit():
        flash("Unable to import registrations. Please check the file.", "danger")
        return redirect(request.referrer or url_for("admin.registrations"))

    party = Party.query.get_or_404(form.party_id.data)
    file_storage = form.file.data
    contents = file_storage.stream.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(contents))

    created = 0
    for row in reader:
        family_name = row.get("family_name") or row.get("name")
        family_email = row.get("family_email") or row.get("email")
        family_phone = row.get("family_phone") or row.get("phone")
        quantity = row.get("quantity") or 1
        status_value = (row.get("status") or "paid").lower()
        expose_contact = (row.get("expose_contact") or "yes").lower() in {"yes", "true", "1"}
        amount_cents = int(row.get("amount_cents") or 0)

        try:
            quantity = int(quantity)
        except ValueError:
            quantity = 1

        try:
            status = RegistrationStatus(status_value)
        except ValueError:
            status = RegistrationStatus.PAID

        registration = Registration(
            party_id=party.id,
            family_name=family_name or "Imported Family",
            family_email=family_email or "unknown@example.com",
            family_phone=family_phone,
            quantity=max(1, quantity),
            status=status,
            expose_contact_to_host=expose_contact,
        )
        db.session.add(registration)
        db.session.flush()

        if status == RegistrationStatus.PAID and amount_cents > 0:
            payment = Payment(
                registration_id=registration.id,
                square_payment_id=f"import-{uuid.uuid4()}",
                status=PaymentStatus.COMPLETED,
                amount_cents=amount_cents,
                paid_at=datetime.utcnow(),
            )
            db.session.add(payment)

        created += 1

    db.session.commit()
    flash(f"Imported {created} registrations for {party.title}.", "success")
    return redirect(request.referrer or url_for("admin.registrations"))

