#!/bin/bash
# Finaliza deploy na EC2 (Amazon Linux 2023) — executar como root ou ec2-user com sudo
set -euo pipefail

get_public_ip() {
  local token ip
  token=$(curl -sf -X PUT "http://169.254.169.254/latest/api/token" \
    -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" 2>/dev/null || true)
  if [ -n "$token" ]; then
    ip=$(curl -sf -H "X-aws-ec2-metadata-token: $token" \
      http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  fi
  if [ -z "${ip:-}" ]; then
    ip=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || true)
  fi
  echo "$ip"
}
PUBLIC_IP="${PUBLIC_IP:-$(get_public_ip)}"
PUBLIC_IP="${PUBLIC_IP:-98.86.118.29}"
APP_DIR=/opt/unifor/app

echo "=== Finalizando deploy Unifor Queimadas - $(date) ==="
echo "IP público: $PUBLIC_IP"

sudo dnf install -y git wget htop docker nginx python3.12 python3.12-pip
sudo systemctl enable --now docker
sudo usermod -aG docker ec2-user || true

if [ ! -x /usr/local/lib/docker/cli-plugins/docker-compose ]; then
  sudo mkdir -p /usr/local/lib/docker/cli-plugins
  sudo curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
    -o /usr/local/lib/docker/cli-plugins/docker-compose
  sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
fi

if ! command -v node >/dev/null 2>&1; then
  curl -fsSL https://rpm.nodesource.com/setup_20.x | sudo bash -
  sudo dnf install -y nodejs
fi

sudo mkdir -p /opt/unifor
if [ ! -d "$APP_DIR/.git" ]; then
  sudo git clone https://github.com/naubergois/ceara-queimadas.git "$APP_DIR"
fi
cd "$APP_DIR"
sudo git pull --ff-only || true

sudo tee backend/.env >/dev/null <<ENVEOF
APP_NAME=Gêmeo Digital Ceará - Queimadas (Unifor)
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=unifor-queimadas-2025-secret
DATABASE_URL=postgresql+asyncpg://ceara:ceara@localhost:5432/queimadas
REDIS_URL=redis://localhost:6379/0
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
NASA_FIRMS_API_KEY=
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://${PUBLIC_IP}","http://${PUBLIC_IP}:5173"]
ENVEOF

if [ ! -x backend/.venv/bin/python ]; then
  python3.12 -m venv backend/.venv
fi
backend/.venv/bin/pip install --upgrade pip -q
backend/.venv/bin/pip install -r backend/requirements-minimal.txt -q

echo "VITE_API_URL=/api/v1" | sudo tee frontend/.env >/dev/null

sudo tee frontend/src/vite-env.d.ts >/dev/null <<'VITEEOF'
/// <reference types="vite/client" />
interface ImportMetaEnv {
  readonly VITE_API_URL: string
}
interface ImportMeta {
  readonly env: ImportMetaEnv
}
VITEEOF
sudo sed -i 's/ title="Auditado"//' frontend/src/components/CardAlerta.tsx

cd frontend
npm install --legacy-peer-deps
npm run build || npx vite build
cd ..

sudo tee /etc/nginx/conf.d/unifor-queimadas.conf >/dev/null <<'NGINXEOF'
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
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000/redoc;
        proxy_set_header Host $host;
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
    }
}
NGINXEOF

sudo nginx -t
sudo systemctl enable nginx
sudo systemctl restart nginx

sudo tee /etc/systemd/system/unifor-backend.service >/dev/null <<'SVCEOF'
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

sudo chown -R ec2-user:ec2-user /opt/unifor
sudo systemctl daemon-reload
sudo systemctl enable unifor-backend
sudo systemctl restart unifor-backend

sleep 3
curl -sf http://127.0.0.1:8000/health | head -c 200
echo ""
curl -sf -o /dev/null -w "nginx HTTP %{http_code}\n" http://127.0.0.1/
systemctl is-active nginx unifor-backend

echo "=== Deploy OK ==="
echo "App: http://${PUBLIC_IP}"
echo "API: http://${PUBLIC_IP}/api/v1"
echo "Docs: http://${PUBLIC_IP}/docs"
