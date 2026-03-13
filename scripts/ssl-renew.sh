#!/usr/bin/env bash
# =============================================================================
# PyPress — SSL Certificate Renewal
# =============================================================================
# Checks and renews Let's Encrypt certificates if they're within 30 days
# of expiry. Safe to run frequently (Certbot skips renewal if not needed).
#
# Usage:
#   make ssl-renew
#   bash scripts/ssl-renew.sh
#
# Recommended cron (runs every 12 hours):
#   0 */12 * * * cd /path/to/pypress && bash scripts/ssl-renew.sh >> logs/ssl-renew.log 2>&1
# =============================================================================

set -euo pipefail

echo "[$(date -Iseconds)] Starting SSL renewal check..."

# Run Certbot renewal (skips if cert is not close to expiry)
docker run --rm \
    -v "$(pwd)/docker/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/docker/certbot/www:/var/www/certbot" \
    certbot/certbot renew --quiet

# If Certbot renewed the cert, copy it to the Nginx SSL directory
CERTBOT_DIR="./docker/certbot/conf/live"
SSL_DIR="./docker/nginx/ssl"

if [ -d "${CERTBOT_DIR}" ]; then
    # Find the domain directory (there should be exactly one)
    DOMAIN_DIR=$(ls -d "${CERTBOT_DIR}"/*/ 2>/dev/null | head -1)
    if [ -n "$DOMAIN_DIR" ]; then
        cp "${DOMAIN_DIR}fullchain.pem" "${SSL_DIR}/fullchain.pem"
        cp "${DOMAIN_DIR}privkey.pem" "${SSL_DIR}/privkey.pem"

        # Reload Nginx to pick up the new cert (graceful, no downtime)
        if docker exec pypress-nginx nginx -t 2>/dev/null; then
            docker exec pypress-nginx nginx -s reload
            echo "[$(date -Iseconds)] Nginx reloaded with renewed certificate."
        else
            echo "[$(date -Iseconds)] WARNING: Nginx config test failed after cert renewal!"
        fi
    fi
fi

echo "[$(date -Iseconds)] SSL renewal check complete."
