"""Application configuration loaded from environment variables."""

from functools import lru_cache

from urllib.parse import urlsplit, urlunsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed settings with defaults for local development."""
    APP_NAME: str = "BookShop API"
    APP_VERSION: str = "0.1.0"
    APP_DESCRIPTION: str = "FastAPI book store API"
    DEBUG: bool = False

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_DAYS: int
    # Refresh-cookie settings are kept in config so local dev and production can
    # use different browser-safe cookie flags without code changes.
    REFRESH_COOKIE_NAME: str
    REFRESH_COOKIE_SECURE: bool
    REFRESH_COOKIE_SAMESITE: str
    REFRESH_COOKIE_PATH: str
    REFRESH_COOKIE_DOMAIN: str | None = None
    REDIS_URL: str
    REFRESH_TOKEN_REDIS_URL: str = "redis://localhost:6381"
    REDIS_REFRESH_PASSWORD: str | None = None
    RATE_LIMIT_STORAGE_URI: str
    SENTRY_DSN: str = ""
    ALLOWED_ORIGINS: list[str] = ["*"]
    GEMINI_API_KEY: str

    # Load from .env during local development and ignore unknown variables.
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def _apply_refresh_redis_password(self) -> "Settings":
        if not self.REDIS_REFRESH_PASSWORD:
            return self
        if "REFRESH_TOKEN_REDIS_URL" in self.model_fields_set:
            return self

        parts = urlsplit(self.REFRESH_TOKEN_REDIS_URL)
        from urllib.parse import quote
        host = parts.hostname or "localhost"
        port = f":{parts.port}" if parts.port else ""
        path = parts.path or "/0"
        password_enc = quote(self.REDIS_REFRESH_PASSWORD, safe="")
        netloc = f":{password_enc}@{host}{port}"
        self.REFRESH_TOKEN_REDIS_URL = urlunsplit((parts.scheme or "redis", netloc, path, "", ""))
        return self


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance to avoid repeated env parsing."""
    return Settings()
