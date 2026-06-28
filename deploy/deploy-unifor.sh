#!/bin/bash
set -euo pipefail

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "=== Deploy Unifor Queimadas - IP: $PUBLIC_IP ==="

# ── Pacotes base ──
sudo dnf install -y --exclude=curl git nginx python3.12 python3.12-pip 2>&1 | tail -3

# ── Node.js 20 ──
curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash - 2>&1 | tail -3
sudo dnf install -y nodejs 2>&1 | tail -3
node --version

# ── Clonar repositório ──
sudo mkdir -p /opt/unifor
sudo chown ec2-user:ec2-user /opt/unifor
cd /opt/unifor
git clone https://github.com/naubergois/ceara-queimadas.git app
cd app

# ── .env backend ──
cat > backend/.env << ENVEOF
APP_NAME=Ceara Digital Twin - Wildfires
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=unifor-queimadas-2025
DATABASE_URL=postgresql+asyncpg://ceara:ceara@localhost:5432/queimadas
REDIS_URL=redis://localhost:6379/0
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://${PUBLIC_IP}","http://${PUBLIC_IP}:8000"]
ENVEOF

# ── Python venv + dependências ──
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip -q
backend/.venv/bin/pip install -r backend/requirements-minimal.txt -q
echo "Python OK"

# ── Frontend: instalar + build ──
cd frontend
cat > .env << FRONTEOF
VITE_API_URL=http://${PUBLIC_IP}/api/v1
FRONTEOF
npm install --legacy-peer-deps 2>&1 | tail -5
npm run build 2>&1 | tail -5
echo "Frontend build OK"
cd ..

# ── Nginx config ──
sudo tee /etc/nginx/conf.d/unifor-queimadas.conf > /dev/null << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    location / {
        root /opt/unifor/app/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }

    location /docs { proxy_pass http://127.0.0.1:8000/docs; }
    location /redoc { proxy_pass http://127.0.0.1:8000/redoc; }
    location /health { proxy_pass http://127.0.0.1:8000/health; }
    location /openapi.json { proxy_pass http://127.0.0.1:8000/openapi.json; }
}
NGINXEOF

sudo nginx -t && sudo systemctl enable nginx && sudo systemctl restart nginx
echo "Nginx OK"

# ── Systemd service backend ──
sudo tee /etc/systemd/system/unifor-backend.service > /dev/null << 'SVCEOF'
[Unit]
Description=Unifor Queimadas Backend (FastAPI)
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/opt/unifor/app/backend
Environment=PATH=/opt/unifor/app/backend/.venv/bin:/usr/local/bin:/usr/bin
ExecStart=/opt/unifor/app/backend/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable unifor-backend
sudo systemctl start unifor-backend
sleep 4
sudo systemctl status unifor-backend --no-pager | head -12

echo ""
echo "=== DEPLOY CONCLUIDO ==="
echo "Frontend: http://${PUBLIC_IP}"
echo "Backend:  http://${PUBLIC_IP}:8000"
echo "API Docs: http://${PUBLIC_IP}/docs"
echo "Health:   http://${PUBLIC_IP}/health"
