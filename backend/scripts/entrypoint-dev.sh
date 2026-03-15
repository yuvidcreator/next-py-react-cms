#!/usr/bin/env bash
# =============================================================================
# PyPress — Development Entrypoint (simplified)
# =============================================================================
# Skips Alembic migrations and health verification for fast startup.
# Used by docker-compose.local.yml for local testing.
# =============================================================================
set -euo pipefail

log() { echo "[$(date -Iseconds)] [entrypoint-dev] $*"; }

DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-5432}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Wait for PostgreSQL
log "Waiting for PostgreSQL..."
for i in $(seq 1 30); do
    if python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('${DB_HOST}', ${DB_PORT})); s.close()" 2>/dev/null; then
        log "PostgreSQL ready"
        break
    fi
    sleep 1
done

# Wait for Redis
log "Waiting for Redis..."
for i in $(seq 1 15); do
    if python3 -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('${REDIS_HOST}', ${REDIS_PORT})); s.close()" 2>/dev/null; then
        log "Redis ready"
        break
    fi
    sleep 1
done

# Verify app imports
log "Verifying app module..."
python3 -c "from app.main import create_app; print('App module OK')" || {
    log "ERROR: App module import failed!"
    exit 1
}

log "Starting: $*"
exec "$@"
