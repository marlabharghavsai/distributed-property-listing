#!/usr/bin/env bash
# =============================================================================
# demonstrate_failover.sh
#
# Demonstrates NGINX failover behavior:
#   1. Verifies the US backend responds to /us/health
#   2. Stops the backend-us container to simulate a failure
#   3. Verifies that /us/health is still served by the EU backend (failover)
#   4. Restarts backend-us to restore the system
# =============================================================================
set -euo pipefail

BASE_URL="http://localhost:8080"
SLEEP_AFTER_STOP=5   # seconds to let NGINX detect the failure

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info()    { echo -e "${YELLOW}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
fail()    { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

echo ""
echo "========================================================"
echo "  NGINX Failover Demonstration"
echo "========================================================"
echo ""

# ── Step 1: Ensure services are running ───────────────────────────────────────
info "Checking that all services are running..."
docker compose ps --services --filter "status=running" | grep -q "backend-us" || \
    fail "backend-us is not running. Run 'docker compose up -d' first."
docker compose ps --services --filter "status=running" | grep -q "backend-eu" || \
    fail "backend-eu is not running. Run 'docker compose up -d' first."
docker compose ps --services --filter "status=running" | grep -q "nginx" || \
    fail "nginx is not running. Run 'docker compose up -d' first."
success "All required services are running."

# ── Step 2: Verify US backend responds directly ───────────────────────────────
info "Verifying backend-us is healthy via NGINX at $BASE_URL/us/health ..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/us/health")
if [ "$STATUS" == "200" ]; then
    success "GET /us/health → HTTP $STATUS (backend-us is serving requests)"
else
    fail "Expected 200 from /us/health but got $STATUS"
fi

# Show which container handled it
info "backend-us recent logs:"
docker logs backend_us --tail=3 2>&1 || true

# ── Step 3: Stop backend-us to simulate failure ───────────────────────────────
info "Stopping backend-us to simulate a regional failure..."
docker stop backend_us
success "backend-us stopped."

info "Waiting ${SLEEP_AFTER_STOP}s for NGINX to detect the failure..."
sleep "$SLEEP_AFTER_STOP"

# ── Step 4: Verify failover — EU serves /us/ requests ────────────────────────
info "Making request to $BASE_URL/us/health (expect EU backend to respond)..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/us/health")
if [ "$STATUS" == "200" ]; then
    success "GET /us/health → HTTP $STATUS even with backend-us DOWN!"
    success "NGINX successfully failed over to backend-eu."
else
    # Restart before failing hard
    docker start backend_us >/dev/null 2>&1 || true
    fail "Expected 200 from /us/health after failover, but got $STATUS"
fi

info "backend-eu recent logs (should show /us/ path served by EU):"
docker logs backend_eu --tail=5 2>&1 || true

# ── Step 5: Restart backend-us ────────────────────────────────────────────────
info "Restarting backend-us to restore the system..."
docker start backend_us
success "backend-us restarted."

info "Waiting 10s for backend-us to become healthy..."
sleep 10

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/us/health")
if [ "$STATUS" == "200" ]; then
    success "GET /us/health → HTTP $STATUS (backend-us restored and responding)"
else
    info "backend-us may still be warming up (got $STATUS) — this is normal."
fi

echo ""
echo "========================================================"
success "Failover demonstration COMPLETE."
echo ""
echo "  Summary:"
echo "    1. backend-us was healthy → /us/health returned 200"
echo "    2. backend-us was stopped (simulated failure)"
echo "    3. /us/health still returned 200 via backend-eu (FAILOVER)"
echo "    4. backend-us was restarted → system restored"
echo "========================================================"
echo ""
