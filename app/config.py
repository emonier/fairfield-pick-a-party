from __future__ import annotations

import os
from dataclasses import dataclass


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "instance", "school_fundraising.db")


@dataclass(slots=True)
class BaseConfig:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me")
    SQLALCHEMY_DATABASE_URI: str = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    SECURITY_SHARED_PASSWORD: str = os.getenv("SECURITY_SHARED_PASSWORD", "school-shared-pass")
    SQUARE_ACCESS_TOKEN: str = os.getenv("SQUARE_ACCESS_TOKEN", "")
    SQUARE_LOCATION_ID: str = os.getenv("SQUARE_LOCATION_ID", "")
    SQUARE_ENVIRONMENT: str = os.getenv("SQUARE_ENVIRONMENT", "sandbox")
    SQUARE_APPLICATION_ID: str = os.getenv("SQUARE_APPLICATION_ID", "")
    SQUARE_WEBHOOK_SIGNATURE_KEY: str = os.getenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "")


@dataclass(slots=True)
class DevelopmentConfig(BaseConfig):
    FLASK_ENV: str = "development"
    DEBUG: bool = True


@dataclass(slots=True)
class ProductionConfig(BaseConfig):
    DEBUG: bool = False


CONFIG_MAP: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None) -> type[BaseConfig]:
    if not name:
        name = os.getenv("FLASK_ENV", "development")
    return CONFIG_MAP.get(name, DevelopmentConfig)

