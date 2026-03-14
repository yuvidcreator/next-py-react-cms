"""
PyPress — Application Configuration (wp-config.php equivalent)

Uses Pydantic BaseSettings to load configuration from environment variables.
Every setting WordPress defines in wp-config.php has a counterpart here.

Settings are loaded once and cached via lru_cache — no redundant parsing.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "PyPress"
    APP_VERSION: str = "0.2.0"
    APP_ENV: str = "production"
    APP_DEBUG: bool = False
    APP_SECRET_KEY: str = "CHANGE-ME-in-production"

    # ── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://pypress:pypress@db:5432/pypress"

    # ── Redis ────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://redis:6379/0"

    # ── JWT Auth ─────────────────────────────────────────────────────────
    JWT_SECRET: str = "CHANGE-ME-in-production"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Cookies ──────────────────────────────────────────────────────────
    COOKIE_DOMAIN: str | None = None
    COOKIE_SECURE: bool = False  # True in production (requires HTTPS)
    COOKIE_SAMESITE: str = "lax"

    # ── CSRF ─────────────────────────────────────────────────────────────
    CSRF_SECRET: str = "CHANGE-ME-in-production"

    # ── Uploads ──────────────────────────────────────────────────────────
    UPLOAD_MAX_SIZE_MB: int = 64
    UPLOAD_DIR: str = "/app/uploads"

    # ── Celery ───────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "/app/logs"

    # ── OAuth2.0 (Phase 9+ — scaffolded) ─────────────────────────────────
    OAUTH_GOOGLE_CLIENT_ID: str = ""
    OAUTH_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_GITHUB_CLIENT_ID: str = ""
    OAUTH_GITHUB_CLIENT_SECRET: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore",
    }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    The lru_cache decorator ensures settings are parsed from env vars
    exactly once, then reused for the lifetime of the process.
    """
    return Settings()
