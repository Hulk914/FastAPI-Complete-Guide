"""Typed environment configuration. Real secrets never belong in source control."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve from this file, so .env does not depend on the process's working directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Read environment values, validate them, and fail startup on unsafe settings."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="forbid",
        hide_input_in_errors=True,
    )

    database_url: str = f"sqlite:///{(PROJECT_ROOT / 'data' / 'app.db').as_posix()}"
    jwt_secret_key: SecretStr  # Required: there is intentionally no usable default key.
    jwt_issuer: str = "products-api"
    jwt_audience: str = "products-api-users"
    access_token_expire_minutes: int = Field(default=20, ge=1, le=120)
    allowed_hosts: list[str] = ["localhost", "127.0.0.1"]

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        """Reject obvious setup mistakes; generate random keys rather than inventing one."""
        secret = value.get_secret_value()
        if len(secret) < 32 or secret == "replace-with-a-generated-secret-key":
            raise ValueError("Generate JWT_SECRET_KEY with secrets.token_hex(32)")
        return value

    @field_validator("allowed_hosts")
    @classmethod
    def validate_hosts(cls, value: list[str]) -> list[str]:
        """Require a deliberate list of hostnames rather than accepting every Host."""
        if not value or "*" in value:
            raise ValueError("Set explicit ALLOWED_HOSTS instead of a wildcard")
        return value


@lru_cache
def get_settings() -> Settings:
    """Parse configuration once per process; missing secrets stop startup early."""
    return Settings()
