#!/bin/bash
# ============================================================
# Sabeel Homeo Clinic - Initial Server Setup
# ============================================================
# Run this ONCE on a FRESH Ubuntu 22.04 server to install
# all prerequisites (Docker, Docker Compose, Caddy, UFW)
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

echo ""
echo "============================================"
echo "  Sabeel Homeo - Initial Server Setup"
echo "============================================"
echo ""

# --- Check if running as root ---
if [ "$EUID" -ne 0 ]; then
    error "Please run as root: sudo bash scripts/setup_server.sh"
fi

# --- Update System ---
log "Updating system packages..."
apt update && apt upgrade -y

# --- Install Prerequisites ---
log "Installing prerequisites..."
apt install -y curl wget git ufw unzip ca-certificates \
    apt-transport-https gnupg lsb-release

# --- Install Docker ---
if ! command -v docker &> /dev/null; then
    log "Installing Docker..."
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    echo \
        "deb [arch=$(dpkg --print-architecture) \
        signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/ubuntu \
        $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    apt update
    apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
    success "Docker installed"
else
    success "Docker already installed"
fi

# --- Enable Docker ---
systemctl enable docker
systemctl start docker
success "Docker daemon started"

# --- Install Docker Compose (standalone) ---
if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log "Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-$(uname -s)-$(uname -m)" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    success "Docker Compose installed"
else
    success "Docker Compose already available"
fi

# --- Install Caddy ---
if ! command -v caddy &> /dev/null; then
    log "Installing Caddy..."
    apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | \
        gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | \
        tee /etc/apt/sources.list.d/caddy-stable.list
    apt update
    apt install -y caddy
    success "Caddy installed"
else
    success "Caddy already installed"
fi

# --- Configure UFW Firewall ---
log "Configuring firewall..."
ufw --force enable
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw --force reload
success "Firewall configured (SSH, HTTP, HTTPS allowed)"

# --- Create Project Directory ---
log "Creating project directory..."
mkdir -p /opt/sabeel-homeo
ln -sf /opt/sabeel-homeo /root/Sabeel-homeo 2>/dev/null || true
success "Directory created at /opt/sabeel-homeo"

# --- Done ---
echo ""
echo "============================================"
echo "  Initial Setup Complete!"
echo "============================================"
echo ""
success "Docker:        $(docker --version)"
success "Docker Compose: $(docker compose version 2>/dev/null || docker-compose --version)"
success "Caddy:         $(caddy version)"
success "Firewall:      enabled (22, 80, 443 open)"
echo ""
echo "Next steps:"
echo ""
echo "  1. Clone your repo into /opt/sabeel-homeo"
echo "     git clone https://github.com/yourusername/Sabeel-homeo.git /opt/sabeel-homeo"
echo ""
echo "  2. Configure environment"
echo "     cd /opt/sabeel-homeo"
echo "     cp .env.example .env"
echo "     nano .env   # fill in your API keys"
echo ""
echo "  3. Run deployment"
echo "     chmod +x scripts/deploy.sh"
echo "     ./scripts/deploy.sh"
echo ""
echo "  4. (Optional) Setup Caddy for WhatsApp panel"
echo "     See docs/WHATSAPP_SETUP.md"
echo ""
