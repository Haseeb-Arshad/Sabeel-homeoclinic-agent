#!/bin/bash
# ============================================================
# Sabeel Homeo Clinic - Deployment Script
# ============================================================
# Usage: ./scripts/deploy.sh [options]
#
# Options:
#   --skip-whatsapp    Skip WhatsApp/Evolution setup
#   --skip-supabase    Skip Supabase setup
#   --full             Full setup including Supabase KB ingestion
# ============================================================

set -e

# --- Colours ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Paths ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/.env"

# --- Defaults ---
SKIP_WHATSAPP=false
SKIP_SUPABASE=false
FULL_SETUP=false

# --- Parse Arguments ---
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-whatsapp)  SKIP_WHATSAPP=true;  shift ;;
        --skip-supabase)  SKIP_SUPABASE=true;  shift ;;
        --full)           FULL_SETUP=true;      shift ;;
        *)                echo "Unknown option: $1"; exit 1 ;;
    esac
done

# --- Helper Functions ---
log()    { echo -e "${BLUE}[INFO]${NC} $1"; }
warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()  { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }
success(){ echo -e "${GREEN}[OK]${NC}   $1"; }

need_env() {
    if [ ! -f "$ENV_FILE" ]; then
        error ".env file not found. Copy .env.example to .env and fill in your values first."
    fi
    source "$ENV_FILE"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Run: curl -fsSL https://get.docker.com | sh"
    fi
    if ! docker info &> /dev/null; then
        error "Docker daemon is not running. Start Docker and try again."
    fi
    success "Docker is available"
}

check_docker_compose() {
    if docker compose version &> /dev/null; then
        DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &> /dev/null; then
        DOCKER_COMPOSE="docker-compose"
    else
        error "Docker Compose not found."
    fi
    success "Docker Compose: $($DOCKER_COMPOSE --version)"
}

# --- Pre-flight Checks ---
echo ""
echo "============================================"
echo "  Sabeel Homeo Clinic - Deployment Script  "
echo "============================================"
echo ""

need_env
check_docker
check_docker_compose

# --- Step 1: Build / Pull Images ---
log "Building Docker images..."
cd "$PROJECT_DIR"
$DOCKER_COMPOSE build api

# --- Step 2: Start API ---
log "Starting FastAPI backend..."
$DOCKER_COMPOSE up -d api

# Wait for API to be healthy
log "Waiting for API to start..."
for i in {1..30}; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        success "API is up at http://localhost:8000"
        break
    fi
    if [ $i -eq 30 ]; then
        error "API failed to start. Check logs: docker compose logs api"
    fi
    sleep 2
done

# --- Step 3: Show Health Check ---
echo ""
echo "--------------------------------------------"
echo "  API Health Check"
echo "--------------------------------------------"
curl -s http://localhost:8000/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/health
echo ""

# --- Step 4: WhatsApp / Evolution Setup ---
if [ "$SKIP_WHATSAPP" = false ]; then
    echo ""
    echo "--------------------------------------------"
    echo "  WhatsApp (Evolution API) Setup"
    echo "--------------------------------------------"
    log "Starting Evolution API..."
    $DOCKER_COMPOSE up -d evolution_api

    log "Waiting for Evolution API to start..."
    for i in {1..20}; do
        if curl -sf http://localhost:8080/instance/fetchInstances \
            -H "apikey: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}" > /dev/null 2>&1; then
            success "Evolution API is up at http://localhost:8080"
            break
        fi
        if [ $i -eq 20 ]; then
            warn "Evolution API may not be ready yet. Check: docker compose logs evolution_api"
        fi
        sleep 2
    done

    echo ""
    echo "============================================"
    echo "  IMPORTANT: Connect WhatsApp"
    echo "============================================"
    echo ""
    echo "1. Install Caddy for HTTPS (recommended for production):"
    echo "   sudo apt install -y caddy"
    echo ""
    echo "2. Add to /etc/caddy/Caddyfile:"
    echo ""
    echo "   wa.yourdomain.com {"
    echo "       reverse_proxy localhost:8080"
    echo "       basicauth /* {"
    echo "           YOUR_PASSWORD JBAhCGf7SHq31"
    echo "       }"
    echo "   }"
    echo ""
    echo "3. Reload Caddy: sudo systemctl reload caddy"
    echo ""
    echo "4. Open https://wa.yourdomain.com in browser"
    echo "5. Login with API key: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}"
    echo "6. Click 'Connect' → scan QR with clinic phone"
    echo ""
    echo "7. After scanning QR, set webhook:"
    echo ""
    if [ -n "$WHATSAPP_WEBHOOK_URL" ]; then
        echo "   curl -X POST ${WHATSAPP_WEBHOOK_URL%/*}/instance/settings \\"
        echo "     -H \"apikey: ${WHATSAPP_API_KEY:-sabeel_clinic_key_2024}\" \\"
        echo "     -H \"Content-Type: application/json\" \\"
        echo "     -d '{\"instanceName\":\"${WHATSAPP_INSTANCE_NAME:-sabeel_homeo}\",\"webhookUrl\":\"${WHATSAPP_WEBHOOK_URL}\",\"events\":[\"messages.upsert\",\"connection.update\"]}'"
    else
        echo "   # Set WHATSAPP_WEBHOOK_URL in .env to your public domain first"
        echo "   # e.g. WHATSAPP_WEBHOOK_URL=https://your-domain.com/webhook/evolution"
    fi
    echo ""
fi

# --- Step 5: Supabase Setup ---
if [ "$SKIP_SUPABASE" = false ]; then
    echo ""
    echo "--------------------------------------------"
    echo "  Supabase (Database + Vector Search)"
    echo "--------------------------------------------"
    if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_SERVICE_ROLE_KEY" ]; then
        warn "Supabase credentials not found in .env."
        echo "  To enable persistence:"
        echo "  1. Create project at https://supabase.com"
        echo "  2. Run supabase/schema.sql in SQL Editor"
        echo "  3. Add SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to .env"
        echo "  4. Run: $DOCKER_COMPOSE restart api"
    else
        success "Supabase credentials found in .env"
        log "Supabase is configured and will be used for data persistence"

        if [ "$FULL_SETUP" = true ]; then
            log "Ingesting website knowledge base into Supabase..."
            $DOCKER_COMPOSE exec -T api python scripts/ingest_wordpress_kb.py
            success "Knowledge base ingestion complete"
        fi
    fi
fi

# --- Final Summary ---
echo ""
echo "============================================"
echo "  Deployment Summary"
echo "============================================"
echo ""
echo "  API:        http://localhost:8000"
echo "  Docs:       http://localhost:8000/docs"
echo "  Evolution:  http://localhost:8080"
echo ""
echo "  Docker containers running:"
$DOCKER_COMPOSE ps --format table 2>/dev/null || $DOCKER_COMPOSE ps
echo ""

if [ "$SKIP_WHATSAPP" = false ]; then
    echo "  Next step: Connect WhatsApp (see above)"
    echo ""
fi

echo "  Useful commands:"
echo "  - View logs:     docker compose logs -f api"
echo "  - Restart API:  docker compose restart api"
echo "  - Stop all:     docker compose down"
echo ""
