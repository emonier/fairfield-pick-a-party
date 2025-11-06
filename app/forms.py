from __future__ import annotations

from datetime import datetime

from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    HiddenField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Email, Length, NumberRange

from .models import PriceUnit


class AdminLoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class PartyForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=255)])
    description = TextAreaField("Description", validators=[DataRequired()])
    event_date = DateTimeLocalField(
        "Event Date",
        format="%Y-%m-%dT%H:%M",
        default=datetime.utcnow,
        validators=[DataRequired()],
    )
    price_cents = IntegerField("Price (cents)", validators=[DataRequired(), NumberRange(min=0)])
    price_unit = SelectField(
        "Price Unit",
        choices=[(unit.value, unit.name.replace("_", " ").title()) for unit in PriceUnit],
        default=PriceUnit.PER_PERSON.value,
        validators=[DataRequired()],
    )
    total_spots = IntegerField("Total Spots", validators=[DataRequired(), NumberRange(min=0)])
    max_tickets_per_order = IntegerField(
        "Max Tickets Per Order", validators=[DataRequired(), NumberRange(min=1)]
    )
    host_contact_name = StringField("Host Name", validators=[Length(max=255)])
    host_contact_email = StringField("Host Email", validators=[Email(), Length(max=255)])
    host_contact_phone = StringField("Host Phone", validators=[Length(max=50)])
    expose_to_hosts = BooleanField("Share attendee contact info with hosts", default=True)


class AddToCartForm(FlaskForm):
    party_id = HiddenField(validators=[DataRequired()])
    quantity = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1, max=10)])


class CheckoutForm(FlaskForm):
    family_name = StringField("Family Name", validators=[DataRequired(), Length(max=255)])
    family_email = StringField("Email", validators=[DataRequired(), Email(), Length(max=255)])
    family_phone = StringField("Contact Phone", validators=[Length(max=50)])
    expose_contact = BooleanField("Share my contact info with party hosts", default=True)


class RegistrationImportForm(FlaskForm):
    party_id = SelectField("Party", coerce=int, validators=[DataRequired()])
    file = FileField(
        "CSV File",
        validators=[
            FileRequired(),
            FileAllowed(["csv"], "Please upload a CSV file."),
        ],
    )

