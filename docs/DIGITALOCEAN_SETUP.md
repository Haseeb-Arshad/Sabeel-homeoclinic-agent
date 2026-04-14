# DigitalOcean Droplet Setup

Complete guide to create a droplet, set up the project, and deploy.

---

## Step 1: Create Droplet

1. Go to [digitalocean.com](https://digitalocean.com) → Create → Droplets
2. Choose:
   - **Region**: Closest to your patients (NY or SF for Pakistan-based clinics)
   - **Image**: Ubuntu 22.04 LTS
   - **Size**: $4-6/mo (1GB RAM足够) — can upgrade later
   - **SSH Key**: Add your local pub key (optional but recommended)
3. Click **Create**

---

## Step 2: Connect to Droplet

```bash
# Get your droplet's IP from DigitalOcean dashboard
ssh root@your-droplet-ip

# You'll be prompted for password if no SSH key added
```

---

## Step 3: Initial Server Setup

Run the one-time server setup script:

```bash
# While SSH'd into the droplet
apt update && apt install -y curl git

# Download and run setup script
# (Upload scripts/deploy.sh, scripts/setup_server.sh, etc. first)
# Or paste contents directly

# Or just run step by step:
curl -fsSL https://get.docker.com | sh
apt install -y caddy
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

---

## Step 4: Create Project Directory

```bash
# On the droplet
mkdir -p /opt/sabeel-homeo
cd /opt/sabeel-homeo
```

**Option A: Clone your GitHub repo directly (recommended)**

```bash
# On the droplet, inside /opt/sabeel-homeo
git init
git remote add origin https://github.com/yourusername/Sabeel-homeo.git
git pull origin main

# Or clone fresh:
git clone https://github.com/yourusername/Sabeel-homeo.git /opt/sabeel-homeo
```

**Option B: Upload files manually via SCP**

```bash
# From YOUR LOCAL machine
scp -r ./app ./scripts ./main.py ./requirements.txt root@your-droplet-ip:/opt/sabeel-homeo/
scp .env.example root@your-droplet-ip:/opt/sabeel-homeo/.env
scp docker-compose.yml root@your-droplet-ip:/opt/sabeel-homeo/
```

---

## Step 5: Configure Environment

```bash
# On the droplet
cd /opt/sabeel-homeo
cp .env.example .env
nano .env
```

Fill in at minimum:

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ELEVENLABS_API_KEY=xi-...
DEEPGRAM_API_KEY=...

# Your public domain (point A record to this droplet's IP)
PUBLIC_BASE_URL=https://yourdomain.com

# WhatsApp - set after Caddy is configured
WHATSAPP_WEBHOOK_URL=https://yourdomain.com/webhook/evolution

# Supabase (optional - add later)
# SUPABASE_URL=https://xxx.supabase.co
# SUPABASE_ANON_KEY=xxx
# SUPABASE_SERVICE_ROLE_KEY=xxx
```

---

## Step 6: Deploy

```bash
# On the droplet
cd /opt/sabeel-homeo

# Make scripts executable
chmod +x scripts/*.sh

# Run deployment
./scripts/deploy.sh
```

---

## Step 7: Set Up Domain (Optional but Required for WhatsApp)

In DigitalOcean → Networking → Domains:

```
# Add domain
yourdomain.com

# Create DNS records:
A    @      → your-droplet-ip    (for your main site)
A    wa     → your-droplet-ip    (for WhatsApp panel subdomain)
```

Then on the droplet, configure Caddy:

```bash
# /etc/caddy/Caddyfile
yourdomain.com {
    reverse_proxy localhost:8000
}

wa.yourdomain.com {
    reverse_proxy localhost:8080
    basicauth /* {
        yourpassword JBAhCGf7SHq31
    }
}
```

```bash
systemctl reload caddy
```

---

## Step 8: Connect WhatsApp

1. Open browser → `https://wa.yourdomain.com`
2. Login with `WHATSAPP_API_KEY` from your `.env`
3. Click **Connect** → scan QR with clinic phone
4. Set webhook via API:

```bash
curl -X POST https://wa.yourdomain.com/instance/settings \
  -H "apikey: sabeel_clinic_key_2024" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "sabeel_homeo",
    "webhookUrl": "https://yourdomain.com/webhook/evolution",
    "events": ["messages.upsert", "connection.update"]
  }'
```

---

## Step 9: Verify Everything Works

```bash
# Check status
./scripts/status.sh

# Test API
curl https://yourdomain.com/health

# Send WhatsApp message to clinic number
# Should get AI reply
```

---

## Updating the Project

```bash
# Pull latest code
cd /opt/sabeel-homeo
git pull origin main

# Rebuild and restart
docker compose up -d --build
```

---

## Useful Commands on Droplet

```bash
# View logs
docker compose logs -f api
docker compose logs -f evolution_api

# Restart services
docker compose restart

# Check disk space
df -h

# Monitor resources
htop

# View WhatsApp session status
curl -s http://localhost:8080/instance/fetchInstances \
  -H "apikey: $(grep WHATSAPP_API_KEY /opt/sabeel-homeo/.env | cut -d= -f2)"
```

---

## Cost Summary

| Item | Cost |
|------|------|
| Droplet (1GB RAM) | $4-6/mo |
| Domain | ~$10/yr |
| Evolution API | Free |
| Supabase (free tier) | Free |
| **Total** | **~$5-7/mo** |
