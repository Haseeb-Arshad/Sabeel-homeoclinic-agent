#!/bin/bash
# ============================================================
# Sabeel Homeo Clinic - Teardown Script
# ============================================================
# Stops and removes all containers, volumes, and images
# WARNING: This deletes ALL data including WhatsApp sessions!
# ============================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()    { echo -e "${BLUE}[INFO]${NC} $1"; }
warn()   { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()  { echo -e "${RED}[ERR]${NC}  $1"; exit 1; }
success(){ echo -e "${GREEN}[OK]${NC}   $1"; }

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "============================================"
echo "  Sabeel Homeo - Teardown"
echo "============================================"
echo ""

# Detect docker compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
elif command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
else
    error "Docker Compose not found."
fi

# Confirmation
echo -e "${YELLOW}WARNING: This will remove ALL containers, volumes, and images!${NC}"
echo ""
echo "  - WhatsApp sessions will be DELETED"
echo "  - All message history will be DELETED"
echo "  - API data will be DELETED"
echo ""
read -p "Are you sure? Type 'yes' to confirm: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

log "Stopping all containers..."
$DOCKER_COMPOSE down

log "Removing volumes (includes WhatsApp session data)..."
$DOCKER_COMPOSE down -v --remove-orphans

log "Removing built images (optional)..."
read -p "Remove API image too? (yes/no): " remove_img
if [ "$remove_img" = "yes" ]; then
    docker rmi sabeel-homeo-api 2>/dev/null || true
    docker rmi sabeel-homeo-api || true
fi

log "Stopping Caddy..."
systemctl stop caddy 2>/dev/null || true

success "Teardown complete"
echo ""
echo "To start fresh:"
echo "  ./scripts/deploy.sh"
echo ""
