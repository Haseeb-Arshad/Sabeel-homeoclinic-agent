# WhatsApp Setup (Evolution API)

This guide connects your clinic WhatsApp number via Evolution API - the cheapest option.

## Quick Start

```bash
# 1. Start Evolution API
docker-compose up -d evolution_api

# 2. Connect WhatsApp (QR code)
# Open浏览器: http://localhost:8080
# API Key when prompted: sabeel_clinic_key_2024
# Click "Connect" → scan QR with your clinic phone
```

## 3. Configure Webhook in Evolution

After connecting, set webhook via API:

```bash
# For LOCAL dev:
curl -X POST http://localhost:8080/instance/settings \
  -H "apikey: sabeel_clinic_key_2024" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "sabeel_homeo",
    "webhookUrl": "http://host.docker.internal:8000/webhook/evolution",
    "webhookByEvents": false,
    "events": ["messages.upsert", "connection.update"]
  }'

# For PRODUCTION (use your public domain):
curl -X POST https://wa.yourdomain.com/instance/settings \
  -H "apikey: sabeel_clinic_key_2024" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "sabeel_homeo",
    "webhookUrl": "https://your-domain.com/webhook/evolution",
    "webhookByEvents": false,
    "events": ["messages.upsert", "connection.update"]
  }'
```

## 4. Start Backend API

```bash
docker-compose up -d api
# Or locally:
venv\Scripts\python.exe main.py
```

## How It Works

```
[Clinic WhatsApp] ←→ [Evolution API] → HTTP POST → [/webhook/evolution] → [AI Service] → [Reply]
```

## Managing the Instance

| Action | API |
|--------|-----|
| Get QR code | `GET /instance/connect/sabeel_homeo` |
| Logout | `DELETE /instance/logout/sabeel_homeo` |
| Restart | `PUT /instance/restart/sabeel_homeo` |
| Check status | `GET /instance/fetchInstances` |

## Reverse Proxy Setup (Production)

On a droplet, access Evolution UI through a subdomain with HTTPS using a reverse proxy.
This also password-protects the panel so strangers can't access it.

### Option 1: Caddy (Recommended — auto SSL)

```bash
# Install Caddy
sudo apt install -y caddy
```

Create `/etc/caddy/Caddyfile`:

```
wa.yourdomain.com {
    reverse_proxy localhost:8080
    basicauth /* {
        yourpassword JBAhCGf7SHq31
    }
}
```

```bash
# Restart Caddy
sudo systemctl reload caddy
```

Done — `https://wa.yourdomain.com` is live with HTTPS and password protection.

---

### Option 2: Nginx

```bash
# Install Nginx
sudo apt install -y nginx
```

Create `/etc/nginx/sites-available/evolution`:

```nginx
server {
    listen 80;
    server_name wa.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name wa.yourdomain.com;

    ssl_certificate     /etc/ssl/certs/your-cert.pem;
    ssl_certificate_key /etc/ssl/private/your-key.pem;

    # Basic password protection
    auth_basic "WhatsApp Panel";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 86400;
    }
}
```

Generate password file:

```bash
sudo apt install -y apache2-utils
sudo htpasswd -bc /etc/nginx/.htpasswd admin yourpassword
```

Enable and restart:

```bash
sudo ln -s /etc/nginx/sites-available/evolution /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

### SSL Certificate (if not using Caddy)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d wa.yourdomain.com
```

---

## Droplet Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Instance not found" | Run `/instance/create` first |
| Webhook not received | Check `WEBHOOK_GLOBAL_URL` in docker-compose |
| Messages not sending | Verify instance is connected (green status) |
| Can't access panel | Check firewall: `sudo ufw status` |
| SSL error | Run certbot or check Caddy is running |

## Production Deployment Steps

On your droplet, run everything in order:

```bash
# 1. Clone repo
git clone your-repo-url
cd Sabeel-homeo

# 2. Copy and fill .env
cp .env.example .env
nano .env   # fill in all values

# 3. Set webhook URL for production
# In .env, set:
WHATSAPP_WEBHOOK_URL=https://your-domain.com/webhook/evolution

# 4. Start services
docker-compose up -d

# 5. Open WhatsApp panel (Caddy/Nginx must be running)
# and scan QR code
open https://wa.yourdomain.com

# 6. Verify webhook is set (should show your API URL)
curl https://wa.yourdomain.com/instance/settings/sabeel_homeo \
  -H "apikey: sabeel_clinic_key_2024"

# 7. Test by sending a WhatsApp message to your clinic number
```

## Cost

- **Free** - Uses your existing WhatsApp number
- Server cost: ~$5/mo (VPS) or free ( Render/Railway )