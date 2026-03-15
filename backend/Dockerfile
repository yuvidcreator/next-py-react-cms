# =============================================================================
# PyPress CMS — Backend Dockerfile (Multi-Stage Build)
# =============================================================================
# WordPress equivalent: The official WordPress Docker image builds PHP +
# Apache + wp-cli in a single stage. PyPress uses a three-stage build:
#
#   Stage 1 (base):        System dependencies + Python packages
#   Stage 2 (development): Dev tools, hot reload, debugging support
#   Stage 3 (production):  Minimal image, non-root user, hardened
#
# The docker-compose.yml selects the target stage:
#   - docker-compose.dev.yml:  target: development
#   - docker-compose.yml:      target: production
#   - docker-compose.test.yml: target: development (for pytest)
#
# SECURITY PROPERTIES:
#   - Production runs as non-root user (pypress, UID 1000)
#   - No build tools in production image (reduces attack surface)
#   - No .git, tests, or docs in production image
#   - Entrypoint runs migrations before starting Uvicorn
#   - Health check verifies DB + Redis connectivity
# =============================================================================


# =============================================================================
# STAGE 1: BASE — System Dependencies + Python Packages
# =============================================================================
# This stage installs everything needed to RUN Python code: system-level
# libraries for PostgreSQL, image processing, and cryptography. It also
# installs all Python dependencies from requirements.txt.
#
# Both development and production stages inherit from this, so package
# installation happens exactly once (Docker layer caching).
# =============================================================================
FROM python:3.12-slim AS base

# ── Metadata (OCI Image Spec) ───────────────────────────────────────────
LABEL maintainer="PyPress Contributors"
LABEL org.opencontainers.image.title="PyPress Backend"
LABEL org.opencontainers.image.description="FastAPI CMS backend — WordPress equivalent"
LABEL org.opencontainers.image.source="https://github.com/pypress/pypress"

# ── Environment: Python Optimization ────────────────────────────────────
# PYTHONUNBUFFERED: Don't buffer stdout/stderr — logs appear immediately
#   in Docker (essential for `docker logs` and log aggregators)
# PYTHONDONTWRITEBYTECODE: Don't create .pyc files (reduces image size,
#   avoids permission issues with non-root user)
# PIP_NO_CACHE_DIR: Don't cache pip downloads (reduces image size)
# PIP_DISABLE_PIP_VERSION_CHECK: Speeds up pip operations
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# ── System Dependencies ─────────────────────────────────────────────────
# These are C libraries that Python packages need at RUNTIME:
#   libpq5:       PostgreSQL client library (needed by asyncpg)
#   libjpeg62:    JPEG support (needed by Pillow for image processing)
#   libwebp7:     WebP support (needed by Pillow for modern image formats)
#   libffi8:      Foreign function interface (needed by cryptography/bcrypt)
#   libmagic1:    File type detection (for upload validation)
#   curl:         Used by health check scripts
#
# We install build dependencies temporarily in a virtual apt package,
# install Python deps, then remove build deps to keep the image small.
RUN apt-get update && apt-get install -y --no-install-recommends \
        # Runtime libraries (kept permanently)
        libpq5 \
        libjpeg62-turbo \
        libwebp7 \
        libffi8 \
        libmagic1 \
        curl \
        # Build dependencies (removed after pip install)
        && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        libwebp-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# ── Application Directory ───────────────────────────────────────────────
WORKDIR /app

# ── Python Dependencies ─────────────────────────────────────────────────
# Copy requirements FIRST (before source code) so Docker caches this
# layer. Dependencies change rarely; code changes often. This means
# `docker build` only re-installs deps when requirements.txt changes.
#
# WordPress equivalent: composer install for PHP dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Remove Build Dependencies ───────────────────────────────────────────
# Build tools are only needed for compiling C extensions during pip install.
# They're NOT needed at runtime, so removing them shrinks the image.
RUN apt-get purge -y --auto-remove \
        build-essential \
        libpq-dev \
        libjpeg62-turbo-dev \
        libwebp-dev \
        libffi-dev \
    && rm -rf /var/lib/apt/lists/*


# =============================================================================
# STAGE 2: DEVELOPMENT — Full Development Environment
# =============================================================================
# Inherits everything from base, then adds:
#   - Dev/test dependencies (pytest, ruff, mypy, debugpy)
#   - Source code (but overridden by volume mounts in docker-compose.dev.yml)
#   - Uvicorn with --reload for hot reloading
#   - Debugger port (5678) for remote debugging with VS Code / PyCharm
#
# This stage runs as ROOT because dev workflows (installing new packages,
# running migrations, etc.) often need write access everywhere.
# WordPress equivalent: running WordPress with WP_DEBUG=true, SCRIPT_DEBUG=true
# =============================================================================
FROM base AS development

# ── Dev/Test Dependencies ────────────────────────────────────────────────
COPY requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

# ── Application Source Code ──────────────────────────────────────────────
# In dev mode, docker-compose.dev.yml mounts the source as a volume,
# so this COPY is only used when running without volume mounts.
COPY . /app/

# ── PYTHONPATH: Ensure imports resolve correctly ─────────────────────────
# The app code lives at /app/app/ (e.g., /app/app/main.py).
# Setting PYTHONPATH=/app means `from app.core.hooks import ...` resolves.
ENV PYTHONPATH=/app

# ── Expose Ports ─────────────────────────────────────────────────────────
# 8000: Uvicorn HTTP server
# 5678: debugpy remote debugger (VS Code / PyCharm attach)
EXPOSE 8000 5678

# ── Development Entrypoint ───────────────────────────────────────────────
# In dev mode, docker-compose.dev.yml overrides this with uvicorn --reload.
# This CMD is a fallback when running the image standalone.
CMD ["uvicorn", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", \
     "--reload", "--reload-dir", "/app/app", "--log-level", "debug", "--factory"]


# =============================================================================
# STAGE 3: PRODUCTION — Minimal, Secure, Non-Root
# =============================================================================
# Inherits from base (NOT development), so dev tools are excluded.
# Key security properties:
#   - Runs as non-root user 'pypress' (UID 1000)
#   - No build tools, no dev dependencies, no debugger
#   - Read-only filesystem where possible (volumes are writable)
#   - Entrypoint script runs migrations, then starts Uvicorn
#   - Gunicorn manages Uvicorn workers for production stability
#
# WordPress equivalent: A locked-down WordPress Docker image with
# file permissions set correctly and debug mode disabled.
# =============================================================================
FROM base AS production

# ── Create Non-Root User ─────────────────────────────────────────────────
# SECURITY: Never run production containers as root. If an attacker
# exploits a vulnerability in the application, they get the permissions
# of the 'pypress' user (which has no sudo, no write access to system
# directories) instead of full root access to the container and
# potentially the host via container escapes.
#
# UID/GID 1000 is conventional for the first non-root user and avoids
# conflicts with system UIDs (0-999).
RUN groupadd --gid 1000 pypress \
    && useradd --uid 1000 --gid pypress --shell /bin/bash --create-home pypress

# ── Application Source Code ──────────────────────────────────────────────
# Copy ONLY what's needed for production. Exclude tests, docs, dev configs.
# The .dockerignore file (created alongside this Dockerfile) handles this,
# but we also explicitly copy only the app directory for clarity.
COPY app/ /app/app/
COPY alembic/ /app/alembic/
COPY alembic.ini /app/alembic.ini
COPY scripts/ /app/scripts/

# ── PYTHONPATH ───────────────────────────────────────────────────────────
ENV PYTHONPATH=/app

# ── Create Writable Directories ─────────────────────────────────────────
# These directories are mounted as Docker volumes in production, but we
# create them with correct ownership so the non-root user can write to
# them even if the volumes aren't mounted (e.g., during testing).
#
# WordPress equivalent: wp-content/uploads, wp-content/plugins, etc.
RUN mkdir -p /app/uploads /app/plugins /app/themes /app/logs /app/backups \
    && chown -R pypress:pypress /app

# ── Entrypoint Script ───────────────────────────────────────────────────
# The entrypoint runs pre-startup tasks (migrations, health checks) before
# handing off to the main process (Uvicorn via Gunicorn).
# WordPress equivalent: the wp-config.php + database upgrade check that
# runs on every WordPress page load, but done ONCE at container start.
COPY scripts/entrypoint.sh /app/scripts/entrypoint.sh
RUN chmod +x /app/scripts/entrypoint.sh

# ── Switch to Non-Root User ──────────────────────────────────────────────
USER pypress

# ── Expose Port ──────────────────────────────────────────────────────────
# Only the HTTP port — no debugger in production
EXPOSE 8000

# ── Health Check ─────────────────────────────────────────────────────────
# Docker uses this to determine if the container is healthy.
# The /api/health endpoint checks DB + Redis connectivity.
# WordPress equivalent: WordPress Site Health check.
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=60s \
    CMD curl -f http://localhost:8000/api/health || exit 1

# ── Entrypoint + Default Command ─────────────────────────────────────────
# ENTRYPOINT runs the migration/startup script.
# CMD provides the default process: Gunicorn managing Uvicorn workers.
# Using Gunicorn as the process manager gives us:
#   - Automatic worker restart on crash
#   - Graceful shutdown with connection draining
#   - Pre-fork worker model for better memory efficiency
#   - Configurable worker count based on CPU cores
ENTRYPOINT ["/app/scripts/entrypoint.sh"]
CMD ["gunicorn", "app.main:create_app", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--timeout", "120", \
     "--graceful-timeout", "30", \
     "--keep-alive", "5", \
     "--max-requests", "1000", \
     "--max-requests-jitter", "50", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "--log-level", "info"]
