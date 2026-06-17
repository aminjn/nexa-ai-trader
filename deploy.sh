#!/bin/bash
# deploy.sh — اجرا روی سرور آروان (Ubuntu 22.04)
set -e

echo "🚀 NEXA AI Trader — Server Deployment"

# ─── 1. System packages ───────────────────────────────────────────
apt-get update -qq
apt-get install -y python3.11 python3-pip python3.11-venv nodejs npm nginx certbot python3-certbot-nginx

# ─── 2. App directory ─────────────────────────────────────────────
APP_DIR="/opt/nexa"
mkdir -p $APP_DIR
cp -r . $APP_DIR
cd $APP_DIR

# ─── 3. Backend — Python venv ─────────────────────────────────────
cd $APP_DIR/backend
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt -q

# Copy env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Edit /opt/nexa/backend/.env and add your GAPGPT_API_KEY!"
fi

# ─── 4. Frontend — build ──────────────────────────────────────────
cd $APP_DIR/frontend
npm install -q
npm run build

# ─── 5. Systemd service for backend ──────────────────────────────
cat > /etc/systemd/system/nexa-backend.service << 'SERVICE'
[Unit]
Description=NEXA AI Trader Backend
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/nexa/backend
Environment=PATH=/opt/nexa/backend/venv/bin
ExecStart=/opt/nexa/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable nexa-backend
systemctl start nexa-backend

# ─── 6. Nginx config ──────────────────────────────────────────────
# Replace YOUR_DOMAIN with your actual domain
DOMAIN="YOUR_DOMAIN.ir"

cat > /etc/nginx/sites-available/nexa << NGINX
server {
    listen 80;
    server_name $DOMAIN;

    # Frontend (React build)
    root /opt/nexa/frontend/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    # Backend API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_read_timeout 300s;
        # SSE support
        proxy_set_header Cache-Control no-cache;
        proxy_buffering off;
    }

    # Websocket
    location /ws/ {
        proxy_pass http://127.0.0.1:8000/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    client_max_body_size 50M;
}
NGINX

ln -sf /etc/nginx/sites-available/nexa /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ""
echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "  1. Edit /opt/nexa/backend/.env  →  add GAPGPT_API_KEY + SECRET_KEY"
echo "  2. Point DNS:  $DOMAIN → $(curl -s ifconfig.me)"
echo "  3. SSL: certbot --nginx -d $DOMAIN"
echo "  4. systemctl restart nexa-backend"
echo ""
echo "  Admin login: admin@nexa.ai / Admin@12345"
