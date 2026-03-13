#!/usr/bin/env bash
# =============================================================================
# PyPress — Network Isolation Validation Script
# =============================================================================
# This script verifies the critical security property of PyPress's Docker
# architecture: the backend API has ZERO public exposure.
#
# Run after `make dev` or `make up`:
#   bash scripts/validate-networks.sh
#
# WordPress comparison: WordPress has no equivalent because PHP and HTML
# share the same process. PyPress deliberately separates them, and this
# script proves the separation is real.
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

PASS=0
FAIL=0

check() {
    local description="$1"
    local result="$2"  # "pass" or "fail"
    local detail="${3:-}"

    if [ "$result" = "pass" ]; then
        echo -e "  ${GREEN}✅ PASS${NC}: $description"
        ((PASS++))
    else
        echo -e "  ${RED}❌ FAIL${NC}: $description"
        [ -n "$detail" ] && echo -e "         ${detail}"
        ((FAIL++))
    fi
}

echo ""
echo "============================================="
echo "  PyPress Network Isolation Validation"
echo "============================================="
echo ""

# ── 1. Verify all containers are running ─────────────────────────────────
echo "1. Container Status"
echo "-------------------"

for svc in db redis backend worker frontend admin nginx; do
    RUNNING=$(docker inspect --format='{{.State.Running}}' "pypress-${svc}" 2>/dev/null || echo "false")
    if [ "$RUNNING" = "true" ]; then
        check "pypress-${svc} is running" "pass"
    else
        check "pypress-${svc} is running" "fail" "Container not found or not running"
    fi
done

echo ""

# ── 2. Verify network assignments ───────────────────────────────────────
echo "2. Network Assignments"
echo "----------------------"

get_networks() {
    docker inspect --format='{{range $k, $v := .NetworkSettings.Networks}}{{$k}} {{end}}' "$1" 2>/dev/null | tr ' ' '\n' | grep -v '^$' | sort
}

# Backend: MUST be on pypress-internal ONLY (no public, no admin-net)
BACKEND_NETS=$(get_networks pypress-backend)
if echo "$BACKEND_NETS" | grep -q "pypress-internal"; then
    check "Backend is on pypress-internal" "pass"
else
    check "Backend is on pypress-internal" "fail" "Networks: $BACKEND_NETS"
fi

if echo "$BACKEND_NETS" | grep -q "pypress-public"; then
    check "Backend is NOT on pypress-public" "fail" "CRITICAL: Backend has public network access!"
else
    check "Backend is NOT on pypress-public" "pass"
fi

# Frontend: MUST be on both pypress-public and pypress-internal
FRONTEND_NETS=$(get_networks pypress-frontend)
if echo "$FRONTEND_NETS" | grep -q "pypress-public" && echo "$FRONTEND_NETS" | grep -q "pypress-internal"; then
    check "Frontend is on pypress-public AND pypress-internal" "pass"
else
    check "Frontend is on pypress-public AND pypress-internal" "fail" "Networks: $FRONTEND_NETS"
fi

# Admin: MUST be on pypress-admin-net and pypress-internal
ADMIN_NETS=$(get_networks pypress-admin)
if echo "$ADMIN_NETS" | grep -q "pypress-admin-net" && echo "$ADMIN_NETS" | grep -q "pypress-internal"; then
    check "Admin is on pypress-admin-net AND pypress-internal" "pass"
else
    check "Admin is on pypress-admin-net AND pypress-internal" "fail" "Networks: $ADMIN_NETS"
fi

# Nginx: MUST be on pypress-public, pypress-admin-net, AND pypress-internal
NGINX_NETS=$(get_networks pypress-nginx)
if echo "$NGINX_NETS" | grep -q "pypress-public" && \
   echo "$NGINX_NETS" | grep -q "pypress-admin-net" && \
   echo "$NGINX_NETS" | grep -q "pypress-internal"; then
    check "Nginx is on all three networks" "pass"
else
    check "Nginx is on all three networks" "fail" "Networks: $NGINX_NETS"
fi

# DB and Redis: MUST be on pypress-internal ONLY
for svc in db redis; do
    SVC_NETS=$(get_networks "pypress-${svc}")
    if echo "$SVC_NETS" | grep -q "pypress-internal" && \
       ! echo "$SVC_NETS" | grep -q "pypress-public" && \
       ! echo "$SVC_NETS" | grep -q "pypress-admin-net"; then
        check "${svc} is on pypress-internal ONLY" "pass"
    else
        check "${svc} is on pypress-internal ONLY" "fail" "Networks: $SVC_NETS"
    fi
done

echo ""

# ── 3. Verify pypress-internal is truly internal ────────────────────────
echo "3. Network Isolation"
echo "--------------------"

INTERNAL_CONFIG=$(docker network inspect pypress-internal --format='{{.Internal}}' 2>/dev/null || echo "unknown")
if [ "$INTERNAL_CONFIG" = "true" ]; then
    check "pypress-internal has 'internal: true' (no host gateway)" "pass"
else
    check "pypress-internal has 'internal: true' (no host gateway)" "fail" "Internal flag: $INTERNAL_CONFIG"
fi

echo ""

# ── 4. Verify port exposure ─────────────────────────────────────────────
echo "4. Port Exposure"
echo "----------------"

get_ports() {
    docker inspect --format='{{range $p, $conf := .NetworkSettings.Ports}}{{$p}}:{{range $conf}}{{.HostPort}}{{end}} {{end}}' "$1" 2>/dev/null
}

# Backend: MUST have NO host port mapping
BACKEND_PORTS=$(get_ports pypress-backend)
if echo "$BACKEND_PORTS" | grep -q "[0-9]"; then
    check "Backend has NO host port mapping" "fail" "CRITICAL: Backend ports exposed: $BACKEND_PORTS"
else
    check "Backend has NO host port mapping" "pass"
fi

# Nginx: MUST have port 80 and/or 443 mapped
NGINX_PORTS=$(get_ports pypress-nginx)
if echo "$NGINX_PORTS" | grep -q "[0-9]"; then
    check "Nginx has host port mapping (80/443)" "pass"
else
    check "Nginx has host port mapping (80/443)" "fail" "No ports exposed"
fi

echo ""

# ── 5. Health checks ────────────────────────────────────────────────────
echo "5. Health Checks"
echo "----------------"

for svc in db redis backend frontend admin nginx; do
    HEALTH=$(docker inspect --format='{{.State.Health.Status}}' "pypress-${svc}" 2>/dev/null || echo "no healthcheck")
    if [ "$HEALTH" = "healthy" ]; then
        check "pypress-${svc} health check" "pass"
    else
        check "pypress-${svc} health check" "fail" "Status: $HEALTH"
    fi
done

echo ""

# ── Summary ──────────────────────────────────────────────────────────────
echo "============================================="
echo "  Results: ${GREEN}${PASS} passed${NC}, ${RED}${FAIL} failed${NC}"
echo "============================================="
echo ""

if [ "$FAIL" -gt 0 ]; then
    echo -e "${RED}Network isolation validation FAILED.${NC}"
    echo "Fix the issues above before deploying to production."
    exit 1
else
    echo -e "${GREEN}All checks passed! Network isolation is correctly enforced.${NC}"
    exit 0
fi
