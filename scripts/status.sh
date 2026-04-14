#!/bin/bash
# ============================================================
# Sabeel Homeo Clinic - Status Check Script
# ============================================================
# Quick health check for all services
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

OK()   { echo -e "${GREEN}[OK]${NC}   $1"; }
FAIL() { echo -e "${RED}[FAIL]${NC} $1"; }
WARN() { echo -e "${YELLOW}[WARN]${NC} $1"; }
INFO() { echo -e "${BLUE}[INFO]${NC} $1"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "============================================"
echo "  Sabeel Homeo - Status Check"
echo "============================================"
echo ""

# Docker
INFO "Docker containers:"
docker compose ps 2>/dev/null || docker-compose ps
echo ""

# API Health
echo -n "API Health: "
if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    RESPONSE=$(curl -s http://localhost:8000/health)
    OK "UP"
    echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
else
    FAIL "DOWN"
fi
echo ""

# Evolution API
echo -n "Evolution API: "
if curl -sf http://localhost:8080/instance/fetchInstances \
    -H "apikey: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}" > /dev/null 2>&1; then
    OK "UP"
else
    WARN "DOWN or not configured"
fi
echo ""

# Supabase
source "$PROJECT_DIR/.env" 2>/dev/null || true
echo -n "Supabase: "
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    if curl -sf -H "apikey: $SUPABASE_SERVICE_ROLE_KEY" \
        "$SUPABASE_URL/rest/v1/" > /dev/null 2>&1; then
        OK "Connected ($SUPABASE_URL)"
    else
        WARN "Configured but not reachable"
    fi
else
    WARN "Not configured (set SUPABASE_URL in .env)"
fi
echo ""

# OpenAI
echo -n "OpenAI: "
if [ -n "$OPENAI_API_KEY" ]; then
    if curl -sf -H "Authorization: Bearer $OPENAI_API_KEY" \
        "https://api.openai.com/v1/models" > /dev/null 2>&1; then
        OK "API key valid"
    else
        WARN "API key may be invalid"
    fi
else
    WARN "Not configured"
fi
echo ""

# WhatsApp Instance Status
echo -n "WhatsApp Instance: "
if curl -sf http://localhost:8080/instance/fetchInstances \
    -H "apikey: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}" 2>/dev/null | \
    grep -q "sabeel_homeo"; then
    STATE=$(curl -s http://localhost:8080/instance/fetchInstances \
        -H "apikey: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}" | \
        python3 -c "import sys,json; d=json.load(sys.stdin); \
        inst=[x for x in d if x.get('instanceName','').lower()=='sabeel_homeo']; \
        print(inst[0].get('status','unknown') if inst else 'not found')" 2>/dev/null || echo "unknown")
    if [ "$STATE" = "open" ] || [ "$STATE" = "connected" ]; then
        OK "Connected ($STATE)"
    else
        WARN "Instance exists but not connected ($STATE)"
    fi
else
    WARN "Instance 'sabeel_homeo' not found"
fi
echo ""

echo "============================================"
echo "  Useful Commands"
echo "============================================"
echo ""
echo "  View API logs:     docker compose logs -f api"
echo "  View WA logs:      docker compose logs -f evolution_api"
echo "  Restart API:       docker compose restart api"
echo "  Restart WA:        docker compose restart evolution_api"
echo "  Full restart:      docker compose restart"
echo "  Redeploy:          docker compose up -d --build"
echo ""
