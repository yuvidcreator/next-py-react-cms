#!/usr/bin/env bash
# =============================================================================
# PyPress CMS — Backend Entrypoint Script
# =============================================================================
# This script runs ONCE when the container starts, BEFORE the main process
# (Gunicorn/Uvicorn) begins serving requests. It ensures the backend is
# fully ready before accepting traffic.
#
# Execution order:
#   1. Wait for PostgreSQL to be ready (TCP connection check)
#   2. Wait for Redis to be ready (PING check)
#   3. Run database migrations (Alembic upgrade head)
#   4. Verify the /api/health endpoint works
#   5. Exec into the main process (Gunicorn → Uvicorn workers)
#
# WordPress equivalent: WordPress checks the database version on every
# page load and runs wp_upgrade() if needed. PyPress does this once at
# startup — faster for every subsequent request.
#
# IMPORTANT: This script uses `exec "$@"` at the end, which replaces
# the shell process with the main process. This means:
#   - Gunicorn becomes PID 1 (receives signals correctly)
#   - `docker stop` sends SIGTERM directly to Gunicorn (graceful shutdown)
#   - No zombie processes from the shell sticking around
# =============================================================================

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────
# These can be overridden via environment variables
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
DB_READY_TIMEOUT="${DB_READY_TIMEOUT:-60}"

REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_READY_TIMEOUT="${REDIS_READY_TIMEOUT:-30}"

MIGRATION_ENABLED="${MIGRATION_ENABLED:-true}"
HEALTH_CHECK_ENABLED="${HEALTH_CHECK_ENABLED:-true}"

# ── Logging Helper ───────────────────────────────────────────────────────
log() {
    echo "[$(date -Iseconds)] [entrypoint] $*"
}

log_error() {
    echo "[$(date -Iseconds)] [entrypoint] ERROR: $*" >&2
}

# =====================================================================
# STEP 1: Wait for PostgreSQL
# =====================================================================
# We cannot run migrations or start the app if the database isn't ready.
# Docker Compose's depends_on with service_healthy helps, but the
# container might start before PostgreSQL finishes its initialization
# (especially on slow machines or first run with database creation).
#
# This loop tries to connect via TCP every 2 seconds, with a configurable
# timeout (default: 60 seconds).
# =====================================================================
wait_for_postgres() {
    log "Waiting for PostgreSQL at ${DB_HOST}:${DB_PORT}..."

    local elapsed=0
    while [ $elapsed -lt "$DB_READY_TIMEOUT" ]; do
        if python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${DB_HOST}', ${DB_PORT}))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
            log "PostgreSQL is ready (took ${elapsed}s)"
            return 0
        fi

        sleep 2
        elapsed=$((elapsed + 2))
    done

    log_error "PostgreSQL not ready after ${DB_READY_TIMEOUT}s — aborting"
    return 1
}

# =====================================================================
# STEP 2: Wait for Redis
# =====================================================================
# Redis is used for caching, sessions, and Celery task queue.
# The backend can technically start without Redis (graceful degradation),
# but we wait for it to ensure full functionality from the first request.
# =====================================================================
wait_for_redis() {
    log "Waiting for Redis at ${REDIS_HOST}:${REDIS_PORT}..."

    local elapsed=0
    while [ $elapsed -lt "$REDIS_READY_TIMEOUT" ]; do
        if python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(2)
try:
    s.connect(('${REDIS_HOST}', ${REDIS_PORT}))
    s.close()
    exit(0)
except:
    exit(1)
" 2>/dev/null; then
            log "Redis is ready (took ${elapsed}s)"
            return 0
        fi

        sleep 2
        elapsed=$((elapsed + 2))
    done

    log_error "Redis not ready after ${REDIS_READY_TIMEOUT}s — aborting"
    return 1
}

# =====================================================================
# STEP 3: Run Database Migrations
# =====================================================================
# Alembic applies any pending database schema changes. This is the
# equivalent of WordPress's wp_upgrade() / dbDelta() function, but
# using proper versioned migrations instead of comparing table schemas.
#
# Benefits over WordPress's approach:
#   - Migrations are versioned and reversible (WordPress's aren't)
#   - Each migration is a Python file in alembic/versions/
#   - `alembic downgrade` can roll back a bad migration
#   - Migration history is stored in the alembic_version table
#
# The --no-auto-upgrade flag can be used to skip migrations in
# environments where they should be run manually (e.g., staging review).
# =====================================================================
run_migrations() {
    if [ "$MIGRATION_ENABLED" != "true" ]; then
        log "Migrations disabled (MIGRATION_ENABLED=${MIGRATION_ENABLED})"
        return 0
    fi

    log "Running database migrations..."

    # Check if there are any pending migrations
    local current_rev
    current_rev=$(cd /app && python3 -m alembic current 2>/dev/null | head -1 || echo "none")
    log "Current migration revision: ${current_rev}"

    # Apply all pending migrations
    if cd /app && python3 -m alembic upgrade head; then
        local new_rev
        new_rev=$(cd /app && python3 -m alembic current 2>/dev/null | head -1 || echo "unknown")
        log "Migrations complete. Current revision: ${new_rev}"
    else
        log_error "Migration failed! The database may be in an inconsistent state."
        log_error "Check the migration files in alembic/versions/ and the database."
        log_error "You can manually run: alembic upgrade head"
        return 1
    fi
}

# =====================================================================
# STEP 4: Pre-Start Health Verification
# =====================================================================
# Before starting the main process, verify that the application can
# actually connect to all its dependencies. This catches configuration
# errors (wrong passwords, wrong hostnames) BEFORE the app starts
# accepting traffic.
#
# This is a lightweight Python check that:
#   - Connects to PostgreSQL (verifies DATABASE_URL is correct)
#   - Connects to Redis (verifies REDIS_URL is correct)
#   - Imports the app module (verifies no import errors)
# =====================================================================
verify_health() {
    if [ "$HEALTH_CHECK_ENABLED" != "true" ]; then
        log "Pre-start health check disabled"
        return 0
    fi

    log "Running pre-start health verification..."

    python3 -c "
import asyncio
import sys

async def verify():
    errors = []

    # 1. Verify database connection
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        import os
        engine = create_async_engine(os.environ['DATABASE_URL'])
        async with engine.connect() as conn:
            await conn.execute(__import__('sqlalchemy').text('SELECT 1'))
        await engine.dispose()
        print('  ✓ PostgreSQL connection OK')
    except Exception as e:
        errors.append(f'PostgreSQL: {e}')
        print(f'  ✗ PostgreSQL: {e}')

    # 2. Verify Redis connection
    try:
        import redis.asyncio as aioredis
        import os
        r = aioredis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
        await r.ping()
        await r.aclose()
        print('  ✓ Redis connection OK')
    except Exception as e:
        errors.append(f'Redis: {e}')
        print(f'  ✗ Redis: {e}')

    # 3. Verify app module imports
    try:
        from app.main import create_app
        print('  ✓ App module imports OK')
    except Exception as e:
        errors.append(f'App import: {e}')
        print(f'  ✗ App import: {e}')

    if errors:
        print(f'\\nHealth check failed with {len(errors)} error(s)')
        sys.exit(1)
    else:
        print('\\nAll pre-start checks passed')

asyncio.run(verify())
" || {
        log_error "Pre-start health check failed!"
        log_error "Fix the configuration and restart the container."
        return 1
    }
}

# =====================================================================
# MAIN: Execute Startup Sequence
# =====================================================================
main() {
    log "================================================="
    log "  PyPress Backend — Starting up"
    log "================================================="
    log "Environment: ${APP_ENV:-production}"
    log "Debug mode:  ${APP_DEBUG:-false}"
    log ""

    # Step 1: Wait for dependencies
    wait_for_postgres
    wait_for_redis

    # Step 2: Run migrations
    run_migrations

    # Step 3: Verify health
    verify_health

    log ""
    log "================================================="
    log "  Startup complete — handing off to main process"
    log "================================================="
    log "Command: $*"
    log ""

    # Step 4: Replace this shell with the main process
    # Using exec ensures Gunicorn becomes PID 1 and receives
    # SIGTERM directly from Docker for graceful shutdown.
    exec "$@"
}

main "$@"
