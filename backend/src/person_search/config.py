"""Typed application and storage configuration."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class ConfigurationError(ValueError):
    """Raised when required configuration is missing or invalid."""


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise ConfigurationError(f"Required environment variable {name} is missing.")
    return value


def _positive_integer(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigurationError(f"Environment variable {name} must be an integer.") from exc
    if value < 0:
        raise ConfigurationError(f"Environment variable {name} must not be negative.")
    return value


def _boolean(environment: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environment.get(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"Environment variable {name} must be a boolean value.")


@dataclass(frozen=True, slots=True)
class PostgresSettings:
    dsn: str
    pool_size: int = 5
    max_overflow: int = 5
    pool_timeout_seconds: int = 10
    connect_timeout_seconds: int = 3

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> PostgresSettings:
        dsn = _required(environment, "PERSON_SEARCH_POSTGRES_DSN")
        try:
            parsed_url = make_url(dsn)
        except ArgumentError as exc:
            raise ConfigurationError(
                "PERSON_SEARCH_POSTGRES_DSN is not a valid database URL."
            ) from exc
        if parsed_url.drivername != "postgresql+psycopg":
            raise ConfigurationError(
                "PERSON_SEARCH_POSTGRES_DSN must use the postgresql+psycopg driver."
            )
        return cls(
            dsn=dsn,
            pool_size=_positive_integer(environment, "PERSON_SEARCH_POSTGRES_POOL_SIZE", 5),
            max_overflow=_positive_integer(environment, "PERSON_SEARCH_POSTGRES_MAX_OVERFLOW", 5),
            pool_timeout_seconds=_positive_integer(
                environment, "PERSON_SEARCH_POSTGRES_POOL_TIMEOUT_SECONDS", 10
            ),
            connect_timeout_seconds=_positive_integer(
                environment, "PERSON_SEARCH_POSTGRES_CONNECT_TIMEOUT_SECONDS", 3
            ),
        )

    def redacted_dsn(self) -> str:
        return make_url(self.dsn).render_as_string(hide_password=True)


@dataclass(frozen=True, slots=True)
class MilvusSettings:
    uri: str
    token: str | None = None
    database: str = "default"
    timeout_seconds: int = 3

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> MilvusSettings:
        return cls(
            uri=_required(environment, "PERSON_SEARCH_MILVUS_URI"),
            token=environment.get("PERSON_SEARCH_MILVUS_TOKEN") or None,
            database=environment.get("PERSON_SEARCH_MILVUS_DATABASE", "default").strip()
            or "default",
            timeout_seconds=_positive_integer(
                environment, "PERSON_SEARCH_MILVUS_TIMEOUT_SECONDS", 3
            ),
        )


@dataclass(frozen=True, slots=True)
class MinioSettings:
    endpoint: str
    access_key: str
    secret_key: str
    bucket: str
    secure: bool = False
    timeout_seconds: int = 3

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> MinioSettings:
        return cls(
            endpoint=_required(environment, "PERSON_SEARCH_MINIO_ENDPOINT"),
            access_key=_required(environment, "PERSON_SEARCH_MINIO_ACCESS_KEY"),
            secret_key=_required(environment, "PERSON_SEARCH_MINIO_SECRET_KEY"),
            bucket=environment.get(
                "PERSON_SEARCH_MINIO_BUCKET", "person-search-frames"
            ).strip()
            or "person-search-frames",
            secure=_boolean(environment, "PERSON_SEARCH_MINIO_SECURE", False),
            timeout_seconds=_positive_integer(
                environment, "PERSON_SEARCH_MINIO_TIMEOUT_SECONDS", 3
            ),
        )


@dataclass(frozen=True, slots=True)
class StorageSettings:
    postgres: PostgresSettings
    milvus: MilvusSettings
    minio: MinioSettings

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str] | None = None
    ) -> StorageSettings:
        values = os.environ if environment is None else environment
        return cls(
            postgres=PostgresSettings.from_environment(values),
            milvus=MilvusSettings.from_environment(values),
            minio=MinioSettings.from_environment(values),
        )

    def secret_values(self) -> tuple[str, ...]:
        postgres_password = make_url(self.postgres.dsn).password
        candidates = (
            self.postgres.dsn,
            postgres_password,
            self.milvus.token,
            self.minio.access_key,
            self.minio.secret_key,
        )
        return tuple(value for value in candidates if value)

    def redacted(self) -> dict[str, Any]:
        return {
            "postgres": {
                "dsn": self.postgres.redacted_dsn(),
                "pool_size": self.postgres.pool_size,
                "max_overflow": self.postgres.max_overflow,
                "pool_timeout_seconds": self.postgres.pool_timeout_seconds,
                "connect_timeout_seconds": self.postgres.connect_timeout_seconds,
            },
            "milvus": {
                "uri": self.milvus.uri,
                "database": self.milvus.database,
                "token": "***" if self.milvus.token else None,
                "timeout_seconds": self.milvus.timeout_seconds,
            },
            "minio": {
                "endpoint": self.minio.endpoint,
                "access_key": "***",
                "secret_key": "***",
                "bucket": self.minio.bucket,
                "secure": self.minio.secure,
                "timeout_seconds": self.minio.timeout_seconds,
            },
        }


class BaseConfig:
    TESTING = False
    JSON_SORT_KEYS = False
    STORAGE_ENABLED = True
    AUTH_COOKIE_NAME = "ps_session"
    AUTH_COOKIE_SECURE = True
    AUTH_COOKIE_SAMESITE = "Lax"
    RATE_LIMITS = {
        "login": (10, 60),
        "search": (30, 60),
        "upload": (10, 60),
        "connection_test": (10, 60),
        "diagnostics": (6, 60),
    }


class DevelopmentConfig(BaseConfig):
    ENVIRONMENT = "development"
    AUTH_COOKIE_SECURE = False


class TestingConfig(BaseConfig):
    ENVIRONMENT = "testing"
    TESTING = True
    STORAGE_ENABLED = False
    AUTH_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    ENVIRONMENT = "production"


CONFIG_BY_ENVIRONMENT: dict[str, type[BaseConfig]] = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def config_for_environment(environment: str | None = None) -> type[BaseConfig]:
    selected = (environment or os.getenv("PERSON_SEARCH_ENV", "development")).lower()
    try:
        return CONFIG_BY_ENVIRONMENT[selected]
    except KeyError as exc:
        supported = ", ".join(sorted(CONFIG_BY_ENVIRONMENT))
        raise ValueError(
            f"Unsupported PERSON_SEARCH_ENV '{selected}'. Expected one of: {supported}."
        ) from exc


def parse_boolean_environment(name: str, default: bool = False) -> bool:
    return _boolean(os.environ, name, default)
