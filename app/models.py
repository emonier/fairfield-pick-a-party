from __future__ import annotations

import enum
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db, login_manager


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PriceUnit(enum.StrEnum):
    PER_CHILD = "per_child"
    PER_PERSON = "per_person"
    PER_FAMILY = "per_family"


class RegistrationStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    CANCELLED = "cancelled"


class PaymentStatus(enum.StrEnum):
    INITIATED = "initiated"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class AdminUser(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "admin_users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id: str) -> AdminUser | None:
    return AdminUser.query.get(int(user_id))


class Party(TimestampMixin, db.Model):
    __tablename__ = "parties"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    event_date = db.Column(db.DateTime, nullable=False)
    price_cents = db.Column(db.Integer, nullable=False)
    price_unit = db.Column(db.Enum(PriceUnit), nullable=False, default=PriceUnit.PER_PERSON)
    total_spots = db.Column(db.Integer, nullable=False)
    max_tickets_per_order = db.Column(db.Integer, nullable=False, default=4)
    host_contact_name = db.Column(db.String(255), nullable=True)
    host_contact_email = db.Column(db.String(255), nullable=True)
    host_contact_phone = db.Column(db.String(50), nullable=True)

    registrations = db.relationship("Registration", back_populates="party", cascade="all, delete-orphan")

    @property
    def spots_taken(self) -> int:
        return sum(reg.quantity for reg in self.registrations if reg.status == RegistrationStatus.PAID)

    @property
    def spots_remaining(self) -> int:
        return max(self.total_spots - self.spots_taken, 0)


class Registration(TimestampMixin, db.Model):
    __tablename__ = "registrations"

    id = db.Column(db.Integer, primary_key=True)
    party_id = db.Column(db.Integer, db.ForeignKey("parties.id"), nullable=False)
    family_name = db.Column(db.String(255), nullable=False)
    family_email = db.Column(db.String(255), nullable=False)
    family_phone = db.Column(db.String(50), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.Enum(RegistrationStatus), nullable=False, default=RegistrationStatus.PENDING)
    expose_contact_to_host = db.Column(db.Boolean, nullable=False, default=True)

    party = db.relationship("Party", back_populates="registrations")
    payments = db.relationship("Payment", back_populates="registration", cascade="all, delete-orphan")

    @property
    def total_amount_cents(self) -> int:
        return self.quantity * self.party.price_cents


class Payment(TimestampMixin, db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    registration_id = db.Column(db.Integer, db.ForeignKey("registrations.id"), nullable=False)
    square_payment_id = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum(PaymentStatus), nullable=False, default=PaymentStatus.INITIATED)
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    paid_at = db.Column(db.DateTime, nullable=True)
    raw_payload = db.Column(db.JSON, nullable=True)

    registration = db.relationship("Registration", back_populates="payments")

