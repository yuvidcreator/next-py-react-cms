"""
PyPress Configuration — equivalent to wp-config.php

Uses Pydantic BaseSettings for environment-based configuration.
Includes OAuth2.0 provider settings for future social login support.
"""
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────
    APP_NAME: str = "PyPress"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-64-chars"
    ALLOWED_HOSTS: list[str] = ["*"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://pypress:pypress@localhost:5432/pypress"
    DATABASE_ECHO: bool = False
    DB_TABLE_PREFIX: str = "pp_"

    # ── Authentication (httpOnly Cookie-Based JWT) ───────────
    JWT_SECRET: str = "jwt-secret-change-me-use-64-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    # Cookie settings — httpOnly is the KEY security measure
    COOKIE_DOMAIN: str = ""  # Empty = current domain only
    COOKIE_SECURE: bool = False  # True in production (HTTPS only)
    COOKIE_SAMESITE: str = "lax"  # "lax" or "strict"
    COOKIE_PATH: str = "/"
    # CSRF Protection
    CSRF_SECRET: str = "csrf-secret-change-me-use-64-chars"
    CSRF_TOKEN_EXPIRE_MINUTES: int = 60

    # ── OAuth2.0 Social Login (Future — Phase 9+) ───────────
    # Google
    OAUTH_GOOGLE_CLIENT_ID: str = ""
    OAUTH_GOOGLE_CLIENT_SECRET: str = ""
    OAUTH_GOOGLE_REDIRECT_URI: str = "/api/v1/auth/oauth/google/callback"
    # GitHub
    OAUTH_GITHUB_CLIENT_ID: str = ""
    OAUTH_GITHUB_CLIENT_SECRET: str = ""
    OAUTH_GITHUB_REDIRECT_URI: str = "/api/v1/auth/oauth/github/callback"
    # Facebook
    OAUTH_FACEBOOK_CLIENT_ID: str = ""
    OAUTH_FACEBOOK_CLIENT_SECRET: str = ""
    OAUTH_FACEBOOK_REDIRECT_URI: str = "/api/v1/auth/oauth/facebook/callback"
    # Generic OIDC provider (self-hosted Keycloak, Auth0, etc.)
    OAUTH_OIDC_ENABLED: bool = False
    OAUTH_OIDC_DISCOVERY_URL: str = ""
    OAUTH_OIDC_CLIENT_ID: str = ""
    OAUTH_OIDC_CLIENT_SECRET: str = ""

    # ── Media / Uploads ──────────────────────────────────────
    UPLOAD_DIR: Path = Path("uploads")
    MAX_UPLOAD_SIZE_MB: int = 64
    ALLOWED_MIME_TYPES: list[str] = [
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf", "video/mp4", "audio/mpeg",
    ]

    # ── Plugin System ────────────────────────────────────────
    PLUGINS_DIR: Path = Path("backend/plugins/installed")
    AUTO_ACTIVATE_PLUGINS: list[str] = []

    # ── Theme System ─────────────────────────────────────────
    THEMES_DIR: Path = Path("backend/themes/installed")
    ACTIVE_THEME: str = "developer_default"

    # ── Caching ──────────────────────────────────────────────
    CACHE_BACKEND: str = "memory"
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Email ────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # ── Pagination ───────────────────────────────────────────
    DEFAULT_POSTS_PER_PAGE: int = 10

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
