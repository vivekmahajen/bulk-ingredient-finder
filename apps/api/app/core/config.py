"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application configuration.

    Values are read from the process environment and, in local development, from
    an ``.env`` file sitting next to ``apps/api``.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Runtime
    environment: str = "development"
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/rasoi_radar"

    # Auth (used from PR-1)
    jwt_secret: str = "change-me-access-secret"
    jwt_refresh_secret: str = "change-me-refresh-secret"

    # External providers
    translate_provider: str = "none"
    translate_api_key: str = ""
    geocode_provider: str = "none"
    geocode_api_key: str = ""

    # CORS — comma-separated extra origins in addition to localhost defaults.
    cors_origins: str = "http://localhost:3000"

    # CORS regex — allow any origin matching this pattern (in addition to the
    # exact list above). Defaults to this project's Vercel deployments so preview
    # URLs (which change per commit) aren't blocked. Set CORS_ORIGIN_REGEX to
    # override, or "" to disable.
    cors_origin_regex: str = r"^https://bulk-ingredient-finder-web[a-z0-9-]*\.vercel\.app$"

    # Tenancy. Multi-tenant by default: self-registration is enabled and every
    # request must carry a valid session (no implicit single-org fallback).
    # Set MULTI_TENANT=false to run in single-restaurant "dogfood" mode.
    multi_tenant: bool = True

    @field_validator("database_url")
    @classmethod
    def _use_asyncpg_driver(cls, v: str) -> str:
        """Normalize managed-Postgres URLs to the asyncpg driver.

        Railway/Heroku/Fly inject a libpq-style ``postgres://`` or
        ``postgresql://`` URL, but the async SQLAlchemy engine needs
        ``postgresql+asyncpg://``. An explicit ``+driver`` is left untouched.
        """
        if v.startswith("postgres://"):
            return "postgresql+asyncpg://" + v[len("postgres://") :]
        if v.startswith("postgresql://"):
            return "postgresql+asyncpg://" + v[len("postgresql://") :]
        return v

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed browser origins: configured values plus localhost dev ports."""
        configured = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
        return sorted(set(configured) | set(defaults))

    @property
    def cors_origin_regex_or_none(self) -> str | None:
        """The origin regex, or None when disabled (empty), for CORSMiddleware."""
        pattern = self.cors_origin_regex.strip()
        return pattern or None


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
