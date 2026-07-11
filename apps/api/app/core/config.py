"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache

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

    # Tenancy
    multi_tenant: bool = False

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"

    @property
    def cors_origin_list(self) -> list[str]:
        """Allowed browser origins: configured values plus localhost dev ports."""
        configured = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        defaults = ["http://localhost:3000", "http://127.0.0.1:3000"]
        return sorted(set(configured) | set(defaults))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
