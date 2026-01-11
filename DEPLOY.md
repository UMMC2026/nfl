# Underdog Signals - Deployment

## Railway Deployment (Recommended)

### 1. Quick Deploy
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login
railway login

# Create project and deploy
railway init
railway up
```

### 2. Set Environment Variables in Railway Dashboard
Go to your project → Variables → Add:
```
DB_URL=sqlite:///./ufa.db
JWT_SECRET_KEY=<generate-with: python -c "import secrets;print(secrets.token_hex(32))">
SPORTS_BOT_TOKEN=<your-telegram-bot-token>
ADMIN_TELEGRAM_IDS=<your-telegram-id>
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
```

### 3. PostgreSQL (Production Database)
In Railway Dashboard:
- Click "New" → "Database" → "PostgreSQL"
- Copy the connection URL
- Update `DB_URL` to: `postgresql://user:pass@host:port/db`

---

## Render Deployment

### 1. Create `render.yaml`:
```yaml
services:
  - type: web
    name: underdog-signals
    runtime: python
    buildCommand: pip install -r requirements-deploy.txt
    startCommand: uvicorn ufa.api.main:app --host 0.0.0.0 --port $PORT
    envVars:
      - key: DB_URL
        sync: false
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: SPORTS_BOT_TOKEN
        sync: false
```

### 2. Connect GitHub and Deploy

---

## Manual VPS Deployment (DigitalOcean/Linode)

### 1. Server Setup
```bash
# SSH into your server
ssh root@your-server-ip

# Install Python
apt update && apt install python3.12 python3.12-venv nginx certbot -y

# Create user
adduser underdog
su - underdog
```

### 2. Clone and Setup
```bash
git clone https://github.com/yourusername/underdog-signals.git
cd underdog-signals
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-deploy.txt
```

### 3. Create Systemd Services

**API Service** (`/etc/systemd/system/underdog-api.service`):
```ini
[Unit]
Description=Underdog Signals API
After=network.target

[Service]
User=underdog
WorkingDirectory=/home/underdog/underdog-signals
Environment="PATH=/home/underdog/underdog-signals/.venv/bin"
EnvironmentFile=/home/underdog/underdog-signals/.env
ExecStart=/home/underdog/underdog-signals/.venv/bin/uvicorn ufa.api.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

**Bot Service** (`/etc/systemd/system/underdog-bot.service`):
```ini
[Unit]
Description=Underdog Telegram Bot
After=network.target

[Service]
User=underdog
WorkingDirectory=/home/underdog/underdog-signals
Environment="PATH=/home/underdog/underdog-signals/.venv/bin"
EnvironmentFile=/home/underdog/underdog-signals/.env
ExecStart=/home/underdog/underdog-signals/.venv/bin/python -m ufa.services.telegram_simple
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Enable Services
```bash
sudo systemctl enable underdog-api underdog-bot
sudo systemctl start underdog-api underdog-bot
```

### 5. Nginx Reverse Proxy
```nginx
server {
    server_name signals.yourdomain.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 6. SSL Certificate
```bash
certbot --nginx -d signals.yourdomain.com
```

---

## Stripe Configuration

### 1. Get API Keys
- Go to https://dashboard.stripe.com/apikeys
- Copy Secret Key (sk_live_xxx) and Publishable Key (pk_live_xxx)

### 2. Create Products
In Stripe Dashboard → Products:
- **Starter**: $19.99/month
- **Pro**: $49.99/month  
- **Whale**: $199.99/month

### 3. Set Webhook
- Go to Developers → Webhooks
- Add endpoint: `https://your-domain.com/payments/webhook`
- Select events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
- Copy signing secret to `STRIPE_WEBHOOK_SECRET`

---

## Quick Test Commands

```bash
# Health check
curl https://your-domain.com/health

# Register user
curl -X POST https://your-domain.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret123"}'

# Login
curl -X POST https://your-domain.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"secret123"}'
```
