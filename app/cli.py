from __future__ import annotations

import getpass

import click

from .extensions import db
from .models import AdminUser


def register_cli(app) -> None:
    @app.cli.command("create-admin")
    @click.argument("email")
    def create_admin(email: str) -> None:
        """Create a new admin user interactively."""

        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm Password: ")
        if password != confirm:
            click.echo("Passwords do not match.")
            return

        with app.app_context():
            existing = AdminUser.query.filter_by(email=email.lower()).first()
            if existing:
                click.echo("Admin with that email already exists.")
                return

            admin = AdminUser(email=email.lower())
            admin.set_password(password)
            db.session.add(admin)
            db.session.commit()
            click.echo("Admin created successfully.")

