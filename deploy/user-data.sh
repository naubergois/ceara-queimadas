#!/bin/bash
# User-data script para EC2 Amazon Linux 2023
# Instala Docker, Node.js, clona o repo e sobe backend + frontend

set -euo pipefail
exec > /var/log/unifor-deploy.log 2>&1

echo "=== Unifor Queimadas Deploy - $(date) ==="

# ── Atualizar sistema ──
dnf update -y
dnf install -y git curl wget htop

# ── Docker ──
dnf install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# ── Docker Compose v2 ──
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# ── Node.js 20 ──
curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
dnf install -y nodejs

# ── Python 3.12 ──
dnf install -y python3.12 python3.12-pip

# ── Nginx (proxy reverso) ──
dnf install -y nginx
systemctl enable nginx

# ── Clonar repositório ──
mkdir -p /opt/unifor
cd /opt/unifor
git clone https://github.com/naubergois/ceara-queimadas.git app
cd app

# ── Configurar .env do backend ──
cat > backend/.env << 'ENVEOF'
APP_NAME=Gêmeo Digital Ceará - Queimadas (Unifor)
APP_VERSION=1.0.0
DEBUG=false
SECRET_KEY=unifor-queimadas-2025-secret
DATABASE_URL=postgresql+asyncpg://ceara:ceara@localhost:5432/queimadas
REDIS_URL=redis://localhost:6379/0
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o
NASA_FIRMS_API_KEY=
CORS_ORIGINS=["http://localhost:3000","http://localhost:5173","http://0.0.0.0:5173"]
ENVEOF

# ── Instalar dependências Python (modo minimal, sem banco) ──
python3.12 -m venv backend/.venv
backend/.venv/bin/pip install --upgrade pip -q
backend/.venv/bin/pip install -r backend/requirements-minimal.txt -q

# ── Instalar dependências Node ──
cd frontend
npm install --legacy-peer-deps
cd ..

# ── Configurar variável de ambiente do frontend ──
cat > frontend/.env << 'FRONTENVEOF'
VITE_API_URL=http://PLACEHOLDER_IP:8000/api/v1
FRONTENVEOF

# Substituir IP real
PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
sed -i "s/PLACEHOLDER_IP/$PUBLIC_IP/g" frontend/.env

# ── Build do frontend ──
cd frontend
npm run build
cd ..

# ── Configurar Nginx ──
cat > /etc/nginx/conf.d/unifor-queimadas.conf << 'NGINXEOF'
server {
    listen 80;
    server_name _;

    # Frontend (arquivos estáticos do build)
    location / {
        root /opt/unifor/app/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }

    # Docs FastAPI
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

nginx -t && systemctl restart nginx

# ── Systemd service para o backend ──
cat > /etc/systemd/system/unifor-backend.service << 'SVCEOF'
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

systemctl daemon-reload
systemctl enable unifor-backend
systemctl start unifor-backend

# ── Permissões ──
chown -R ec2-user:ec2-user /opt/unifor

echo "=== Deploy concluído: $(date) ==="
echo "Backend: http://$PUBLIC_IP:8000"
echo "Frontend: http://$PUBLIC_IP"
echo "API Docs: http://$PUBLIC_IP/docs"
