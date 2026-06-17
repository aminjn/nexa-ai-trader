#!/bin/bash
set -e
echo "🚀 NEXA AI Trader — نصب خودکار"

# ─── مسیرها ───────────────────────────────────────────────────────
REPO_DIR="/home/ubuntu/nexa"
BACKEND="$REPO_DIR/backend"
FRONTEND="$REPO_DIR/frontend"

# ─── 1. پایتون ────────────────────────────────────────────────────
echo "📦 نصب Python..."
apt-get update -qq
# روی Ubuntu 24.04 پایتون 3.12 پیش‌فرض است (distutils در 3.12 حذف شده)
apt-get install -y python3 python3-venv python3-dev python3-pip build-essential curl
PY=$(command -v python3.12 || command -v python3)
echo "   استفاده از: $PY ($($PY --version))"

# ─── 2. Node.js ───────────────────────────────────────────────────
echo "📦 نصب Node.js..."
if ! command -v node &>/dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs
fi

# ─── 3. nginx ─────────────────────────────────────────────────────
apt-get install -y nginx

# ─── 4. Backend venv ──────────────────────────────────────────────
echo "🐍 نصب dependencies بک‌اند..."
cd "$BACKEND"
$PY -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt

# ─── 5. فایل .env ────────────────────────────────────────────────
if [ ! -f "$BACKEND/.env" ]; then
    cp "$BACKEND/.env.example" "$BACKEND/.env"
fi

# ─── 6. Build فرانت‌اند ───────────────────────────────────────────
echo "⚛️ بیلد فرانت‌اند..."
cd "$FRONTEND"
npm install -q
npm run build

# ─── 7. Systemd service ───────────────────────────────────────────
echo "⚙️ تنظیم سرویس..."
cat > /etc/systemd/system/nexa.service << EOF
[Unit]
Description=NEXA AI Trader Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$BACKEND
Environment=PATH=$BACKEND/venv/bin:/usr/bin:/bin
ExecStart=$BACKEND/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable nexa
systemctl restart nexa

# ─── 8. Nginx ─────────────────────────────────────────────────────
echo "🌐 تنظیم nginx..."
cat > /etc/nginx/sites-available/nexa << EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root $FRONTEND/dist;
    index index.html;

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_read_timeout 300s;
        proxy_buffering off;
    }
}
EOF

ln -sf /etc/nginx/sites-available/nexa /etc/nginx/sites-enabled/nexa
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo ""
echo "✅ نصب کامل شد!"
echo ""
echo "⚠️  حالا باید .env رو تنظیم کنی:"
echo "   nano $BACKEND/.env"
echo ""
echo "   بعد از ذخیره:"
echo "   systemctl restart nexa"
echo ""
echo "🌐 سایت: http://$(curl -s ifconfig.me)"
echo "👤 ادمین: admin@nexa.ai / Admin@12345"
