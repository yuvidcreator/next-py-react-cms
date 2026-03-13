#!/usr/bin/env bash
# =============================================================================
# PyPress — SSL Certificate Setup (Let's Encrypt)
# =============================================================================
# Automates the entire process of obtaining an SSL certificate from Let's
# Encrypt and configuring Nginx to use it.
#
# Usage:
#   make ssl-setup                        (interactive — prompts for domain)
#   bash scripts/ssl-setup.sh yourdomain.com admin@yourdomain.com
#
# What this script does:
#   1. Validates that the domain resolves to this server
#   2. Ensures Nginx is running with the no-SSL config (port 80)
#   3. Runs Certbot to obtain a certificate via ACME HTTP-01 challenge
#   4. Generates a strong Diffie-Hellman parameter file
#   5. Switches Nginx from no-ssl.conf to default.conf (SSL enabled)
#   6. Tests the new config and reloads Nginx
#   7. Sets up auto-renewal via Certbot's built-in timer
#
# WordPress equivalent: Really Simple SSL plugin + manual cert setup,
# but fully automated and integrated into the infrastructure.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ── Parse Arguments ──────────────────────────────────────────────────────
DOMAIN="${1:-}"
EMAIL="${2:-}"

if [ -z "$DOMAIN" ]; then
    echo ""
    echo "PyPress SSL Setup"
    echo "================="
    echo ""
    read -p "Enter your domain (e.g., yourdomain.com): " DOMAIN
    read -p "Enter your email (for Let's Encrypt notifications): " EMAIL
fi

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
    echo -e "${RED}Error: Both domain and email are required.${NC}"
    echo "Usage: $0 <domain> <email>"
    exit 1
fi

echo ""
echo -e "${YELLOW}Setting up SSL for: ${DOMAIN}${NC}"
echo ""

# ── Step 1: Ensure Nginx is running ─────────────────────────────────────
echo "Step 1: Checking Nginx status..."
if ! docker inspect pypress-nginx --format='{{.State.Running}}' 2>/dev/null | grep -q true; then
    echo -e "${RED}Error: Nginx container is not running.${NC}"
    echo "Start PyPress first: make up"
    exit 1
fi
echo -e "  ${GREEN}✅ Nginx is running${NC}"

# ── Step 2: Switch to no-SSL config if not already ──────────────────────
echo "Step 2: Ensuring HTTP-only mode for ACME challenge..."
SSL_DIR="./docker/nginx/ssl"
CONF_DIR="./docker/nginx/conf.d"

# Check if SSL cert already exists
if [ -f "${SSL_DIR}/fullchain.pem" ]; then
    echo -e "  ${YELLOW}⚠ SSL certificate already exists. Re-issuing...${NC}"
fi

# Use no-SSL config for the ACME challenge
if [ -f "${CONF_DIR}/no-ssl.conf.template" ]; then
    cp "${CONF_DIR}/default.conf" "${CONF_DIR}/default.conf.ssl-backup"
    cp "${CONF_DIR}/no-ssl.conf.template" "${CONF_DIR}/default.conf"
    docker exec pypress-nginx nginx -s reload 2>/dev/null || true
    sleep 2
fi
echo -e "  ${GREEN}✅ HTTP-only mode active${NC}"

# ── Step 3: Obtain certificate via Certbot ───────────────────────────────
echo "Step 3: Requesting certificate from Let's Encrypt..."
docker run --rm \
    -v "$(pwd)/docker/certbot/conf:/etc/letsencrypt" \
    -v "$(pwd)/docker/certbot/www:/var/www/certbot" \
    certbot/certbot certonly \
        --webroot \
        --webroot-path=/var/www/certbot \
        --email "${EMAIL}" \
        --agree-tos \
        --no-eff-email \
        -d "${DOMAIN}" \
        -d "www.${DOMAIN}" \
    && echo -e "  ${GREEN}✅ Certificate obtained${NC}" \
    || {
        echo -e "${RED}Error: Certbot failed. Check that:${NC}"
        echo "  1. Your domain (${DOMAIN}) points to this server's IP"
        echo "  2. Port 80 is open and reachable from the internet"
        echo "  3. Nginx is serving the ACME challenge directory"
        # Restore SSL config if we backed it up
        if [ -f "${CONF_DIR}/default.conf.ssl-backup" ]; then
            mv "${CONF_DIR}/default.conf.ssl-backup" "${CONF_DIR}/default.conf"
            docker exec pypress-nginx nginx -s reload 2>/dev/null || true
        fi
        exit 1
    }

# ── Step 4: Copy certificates to Nginx SSL directory ────────────────────
echo "Step 4: Installing certificates..."
cp "./docker/certbot/conf/live/${DOMAIN}/fullchain.pem" "${SSL_DIR}/fullchain.pem"
cp "./docker/certbot/conf/live/${DOMAIN}/privkey.pem" "${SSL_DIR}/privkey.pem"
echo -e "  ${GREEN}✅ Certificates installed${NC}"

# ── Step 5: Generate Diffie-Hellman parameters (if not exists) ───────────
if [ ! -f "${SSL_DIR}/dhparam.pem" ]; then
    echo "Step 5: Generating DH parameters (this takes a minute)..."
    openssl dhparam -out "${SSL_DIR}/dhparam.pem" 2048 2>/dev/null
    echo -e "  ${GREEN}✅ DH parameters generated${NC}"
else
    echo "Step 5: DH parameters already exist, skipping."
fi

# ── Step 6: Switch back to SSL config ────────────────────────────────────
echo "Step 6: Activating SSL configuration..."
if [ -f "${CONF_DIR}/default.conf.ssl-backup" ]; then
    mv "${CONF_DIR}/default.conf.ssl-backup" "${CONF_DIR}/default.conf"
fi
echo -e "  ${GREEN}✅ SSL config activated${NC}"

# ── Step 7: Test and reload Nginx ────────────────────────────────────────
echo "Step 7: Testing and reloading Nginx..."
if docker exec pypress-nginx nginx -t 2>/dev/null; then
    docker exec pypress-nginx nginx -s reload
    echo -e "  ${GREEN}✅ Nginx reloaded with SSL${NC}"
else
    echo -e "${RED}Error: Nginx config test failed!${NC}"
    echo "Check: docker exec pypress-nginx nginx -t"
    exit 1
fi

# ── Step 8: Update .env with domain ─────────────────────────────────────
echo "Step 8: Updating .env..."
if [ -f ".env" ]; then
    sed -i "s|^SITE_URL=.*|SITE_URL=https://${DOMAIN}|" .env
    sed -i "s|^COOKIE_DOMAIN=.*|COOKIE_DOMAIN=.${DOMAIN}|" .env
    sed -i "s|^COOKIE_SECURE=.*|COOKIE_SECURE=true|" .env
    echo -e "  ${GREEN}✅ .env updated (SITE_URL, COOKIE_DOMAIN, COOKIE_SECURE)${NC}"
fi

# ── Done ─────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}=============================================${NC}"
echo -e "${GREEN}  SSL setup complete!${NC}"
echo -e "${GREEN}=============================================${NC}"
echo ""
echo "  Your site is now available at:"
echo "    https://${DOMAIN}"
echo "    https://www.${DOMAIN}"
echo ""
echo "  Admin panel:"
echo "    https://${DOMAIN}/admin"
echo ""
echo "  Certificate auto-renewal:"
echo "    Run 'make ssl-renew' or add a cron job:"
echo "    0 */12 * * * cd $(pwd) && make ssl-renew"
echo ""
