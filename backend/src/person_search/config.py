"""Application configuration for the skeleton phase."""

from __future__ import annotations

import os
from typing import Any


class BaseConfig:
    """Settings shared by all environments."""

    TESTING = False
    JSON_SORT_KEYS = False


class DevelopmentConfig(BaseConfig):
    """Local development defaults."""

    ENVIRONMENT = "development"


class TestingConfig(BaseConfig):
    """Deterministic settings used by the automated test suite."""

    ENVIRONMENT = "testing"
    TESTING = True


class ProductionConfig(BaseConfig):
    """Production-shaped settings; validation is added with real dependencies."""

    ENVIRONMENT = "production"


CONFIG_BY_ENVIRONMENT: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_for_environment(environment: str | None = None) -> type[BaseConfig]:
    """Resolve a known configuration class or fail fast for a typo."""

    selected = (environment or os.getenv("PERSON_SEARCH_ENV", "development")).lower()

    try:
        return CONFIG_BY_ENVIRONMENT[selected]
    except KeyError as exc:
        supported = ", ".join(sorted(CONFIG_BY_ENVIRONMENT))
        raise ValueError(
            f"Unsupported PERSON_SEARCH_ENV '{selected}'. Expected one of: {supported}."
        ) from exc


def parse_boolean_environment(name: str, default: bool = False) -> bool:
    """Parse an explicit environment boolean for command-line entrypoints."""

    raw_value: Any = os.getenv(name)
    if raw_value is None:
        return default

    normalized = str(raw_value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False

    raise ValueError(f"Environment variable {name} must be a boolean value.")
