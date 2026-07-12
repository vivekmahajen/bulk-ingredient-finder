"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", ""})


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

    # Web price discovery (optional). "claude" uses the Anthropic Messages API
    # with the web-search tool to find bulk sellers + prices for an ingredient
    # near the org's location; "none" disables it. Enable by setting
    # DISCOVERY_PROVIDER=claude (the default) and ANTHROPIC_API_KEY.
    discovery_provider: str = "claude"
    anthropic_api_key: str = ""
    discovery_model: str = "claude-sonnet-5"
    # Web search can legitimately take a while; the proxy in front of the API
    # tolerates a long round-trip, so give the upstream call generous headroom.
    discovery_timeout_s: float = 90.0

    # Invoice capture (PR-9). Extraction uses ANTHROPIC_API_KEY above; set
    # EXTRACT_PROVIDER=null to run the whole pipeline off fixtures (tests/CI).
    extract_provider: str = "claude"
    extraction_model: str = "claude-sonnet-4-6"
    extraction_timeout_s: float = 60.0
    extraction_retries: int = 2
    extractions_per_day: int = 25

    # Object storage for invoice images.
    storage_provider: str = "local"  # "local" | "s3"
    storage_local_dir: str = "var/uploads"
    s3_endpoint: str = ""
    s3_bucket: str = ""
    s3_region: str = "auto"
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""

    # Upload hardening bounds.
    max_upload_mb: int = 15
    max_pages: int = 6

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
    def _normalize_database_url(cls, v: str) -> str:
        """Make managed-Postgres URLs work with the async (asyncpg) driver.

        Two fixups:
        1. Scheme — Railway/Neon/Heroku inject a libpq-style ``postgres://`` /
           ``postgresql://`` URL, but the async engine needs
           ``postgresql+asyncpg://``. An explicit ``+driver`` is left untouched.
        2. Query string — libpq options like ``sslmode`` and ``channel_binding``
           (e.g. Neon appends ``?sslmode=require&channel_binding=require``) are
           not valid asyncpg connect kwargs and raise at connect time. Drop them;
           TLS is configured via connect args instead (see
           ``database_connect_args``).
        """
        if v.startswith("postgres://"):
            v = "postgresql+asyncpg://" + v[len("postgres://") :]
        elif v.startswith("postgresql://"):
            v = "postgresql+asyncpg://" + v[len("postgresql://") :]
        parts = urlsplit(v)
        if parts.query or parts.fragment:
            v = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        return v

    @property
    def database_connect_args(self) -> dict[str, object]:
        """asyncpg connect args. Enable TLS for remote hosts (managed Postgres
        requires it); local dev/test Postgres runs without SSL."""
        host = urlsplit(self.database_url).hostname or ""
        if host in _LOCAL_HOSTS:
            return {}
        return {"ssl": "require"}

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
