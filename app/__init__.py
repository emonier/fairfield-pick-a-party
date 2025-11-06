from __future__ import annotations

from flask import Flask

from .cli import register_cli
from .config import get_config
from .extensions import csrf, db, login_manager, migrate
from .routes.admin import admin_bp
from .routes.family import family_bp
from .routes.webhooks import webhooks_bp


def create_app(config_name: str | None = None) -> Flask:
    """Application factory for the fundraising portal."""

    app = Flask(__name__, instance_relative_config=True)
    config_obj = get_config(config_name)
    app.config.from_object(config_obj)

    register_extensions(app)
    register_blueprints(app)
    register_cli(app)

    return app


def register_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(family_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(webhooks_bp)

