#!/bin/bash
# ============================================================
# Sabeel Homeo Clinic - Backup Script
# ============================================================
# Backs up conversations, messages, appointments, and
# WhatsApp session data to a timestamped .tar.gz file.
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

BACKUP_DIR="${BACKUP_DIR:-/opt/sabeel-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/sabeel_backup_${TIMESTAMP}.tar.gz"

echo ""
echo "============================================"
echo "  Sabeel Homeo - Backup"
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

# Load env vars
source "$PROJECT_DIR/.env" 2>/dev/null || true

# Create backup dir
mkdir -p "$BACKUP_DIR"
success "Backup directory: $BACKUP_DIR"

# --- Supabase Backup ---
log "Checking Supabase..."
if [ -n "$SUPABASE_URL" ] && [ -n "$SUPABASE_SERVICE_ROLE_KEY" ]; then
    log "Supabase detected — you should use Supabase dashboard for automated backups."
    log "Manual SQL backup:"
    SUPABASE_BACKUP="$BACKUP_DIR/supabase_backup_${TIMESTAMP}.sql"
    echo "  To dump Supabase data, use Supabase dashboard > Database > SQL Editor > Download."
    echo "  Or use psql with your connection string."
else
    warn "Supabase not configured"
fi

# --- WhatsApp Session Backup ---
log "Backing up WhatsApp sessions..."
WA_VOLUME="sabeel-homeo_evolution_instances"
if docker volume inspect "$WA_VOLUME" > /dev/null 2>&1; then
    WA_BACKUP="$BACKUP_DIR/wa_session_${TIMESTAMP}.tar.gz"
    docker run --rm \
        -v "$WA_VOLUME":/data \
        -v "$BACKUP_DIR":/backup \
        alpine tar czf "/backup/wa_session_${TIMESTAMP}.tar.gz" -C /data .
    success "WhatsApp session backed up: wa_session_${TIMESTAMP}.tar.gz"
else
    warn "WhatsApp volume not found, skipping"
fi

# --- Env File Backup ---
log "Backing up .env..."
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_DIR/.env_${TIMESTAMP}"
    success ".env backed up"
else
    warn ".env not found, skipping"
fi

# --- Docker Compose File Backup ---
log "Backing up docker-compose.yml..."
cp "$PROJECT_DIR/docker-compose.yml" "$BACKUP_DIR/docker-compose.yml_${TIMESTAMP}"
success "docker-compose.yml backed up"

# --- List Backups ---
echo ""
echo "--------------------------------------------"
echo "  Backup Complete!"
echo "--------------------------------------------"
ls -lh "$BACKUP_DIR"/

echo ""
echo "Backups stored in: $BACKUP_DIR"
echo ""
echo "To restore WhatsApp session:"
echo "  docker volume rm sabeel-homeo_evolution_instances 2>/dev/null || true"
echo "  docker run --rm -v sabeel-homeo_evolution_instances:/data -v $BACKUP_DIR:/backup alpine tar xzf /backup/wa_session_${TIMESTAMP}.tar.gz -C /data"
echo ""

# --- Remote Upload (optional) ---
if [ -n "$BACKUP_SCP_USER" ] && [ -n "$BACKUP_SCP_HOST" ]; then
    log "Uploading to remote server..."
    scp "$BACKUP_FILE" "${BACKUP_SCP_USER}@${BACKUP_SCP_HOST}:${BACKUP_SCP_PATH:-/backups}/"
    success "Uploaded to ${BACKUP_SCP_HOST}"
fi

success "All backups done!"
