# 📦 Guia de Instalação — Gêmeo Digital Queimadas Ceará

> Instalação completa do zero para desenvolvimento ou produção.

---

## Índice

- [Pré-requisitos](#pré-requisitos)
- [Setup Rápido (Docker)](#setup-rápido-docker)
- [Setup Manual (desenvolvimento)](#setup-manual-desenvolvimento)
- [Deploy AWS EC2](#deploy-aws-ec2)
- [Solução de Problemas](#solução-de-problemas)

---

## Pré-requisitos

| Recurso | Versão Mínima | Obrigatório |
|---------|--------------|-------------|
| **Docker** | 24+ | ✅ (setup rápido) |
| **Docker Compose** | v2 | ✅ (setup rápido) |
| **Python** | 3.12+ | ✅ (desenvolvimento) |
| **Node.js** | 20+ | ✅ (frontend) |
| **PostgreSQL + PostGIS** | 16 + 3.4 | ✅ (modo completo) |
| **Redis** | 7+ | ✅ (cache/coleta) |

### Chaves de API Necessárias

| Chave | Obrigatória | Onde obter |
|-------|-------------|------------|
| `DEEPSEEK_API_KEY` | ✅ | [platform.deepseek.com](https://platform.deepseek.com) |
| `NASA_FIRMS_API_KEY` | ✅ | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/) |
| `INPE_API_KEY` | ❌ | [queimadas.dgi.inpe.br](https://queimadas.dgi.inpe.br) |
| `FUNCEME_API_KEY` | ❌ | [funceme.br](https://www.funceme.br) |
| `INMET_TOKEN` | ❌ | [apitempo.inmet.gov.br](https://apitempo.inmet.gov.br) |
| `MAPBIOMAS_TOKEN` | ❌ | [mapbiomas.org](https://mapbiomas.org) |

---

## Setup Rápido (Docker)

### 1. Clone

```bash
git clone https://github.com/naubergois/ceara-queimadas.git
cd ceara-queimadas
```

### 2. Configure o .env

```bash
cp backend/.env.example backend/.env
# Edite com suas chaves:
#   DEEPSEEK_API_KEY, NASA_FIRMS_API_KEY
nano backend/.env
```

### 3. Suba os serviços

```bash
cd docker
docker compose up -d
```

Aguardar healthchecks (~30s). Verifique:

```bash
docker compose ps
# Todos devem estar "healthy" ou "Up"
```

### 4. Verifique

| Serviço | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API FastAPI | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

---

## Setup Manual (desenvolvimento)

### Backend

```bash
# 1. Ambiente virtual
cd backend
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Dependências
pip install -r requirements.txt

# 3. Configuração
cp .env.example .env
# Edite .env com suas credenciais

# 4. Banco de dados (se for usar modo completo)
docker compose -f ../docker/docker-compose.yml up -d db

# 5. Inicie o servidor
uvicorn app.main:app --reload --port 8000
```

### Frontend (em outro terminal)

```bash
cd frontend
npm install
npm run dev
# Abre em http://localhost:5173
```

### Modo Standalone (sem banco)

O backend funciona **sem PostgreSQL** em modo autônomo, usando apenas:
- NASA FIRMS → dados de focos via API HTTP
- Open-Meteo → dados climáticos
- FAISS + fastembed → RAG do chat da pesquisa

Para rodar neste modo:

```bash
cd backend
pip install -r requirements-minimal.txt
uvicorn app.main:app --reload --port 8000
```

O FastAPI detecta a ausência do banco e carrega apenas os endpoints sem banco.

---

## Deploy AWS EC2

### Opção 1: Deploy Automático (user-data)

Crie uma instância Amazon Linux 2023 e cole o conteudo de `user-data.sh` no campo **User data** ao lançar. O script:

1. Instala Docker, Node.js, Python 3.12, Nginx
2. Clona o repositório
3. Configura `.env` com IP público
4. Builda o frontend
5. Configura Nginx como reverse proxy
6. Registra o backend como serviço systemd

### Opção 2: Deploy Manual

```bash
# Conecte-se e execute:
sudo bash deploy/deploy-unifor.sh
```

### Verificação pós-deploy

```bash
# Health check da API
curl http://SEU_IP/health

# Ver servicos
sudo systemctl status unifor-backend
sudo systemctl status nginx

# Logs
sudo journalctl -u unifor-backend -f --no-pager
```

---

## Solução de Problemas

| Problema | Causa Provável | Solução |
|----------|---------------|---------|
| Backend não sobe | Porta 8000 ocupada | `lsof -i :8000` e mate o processo |
| DB connection failed | PostgreSQL não iniciou | `docker compose up -d db` |
| Frontend em branco | CORS não configurado | Verifique `CORS_ORIGINS` no `.env` |
| API retorna 500 | Chave FIRMS inválida | Verifique `NASA_FIRMS_API_KEY` |
| Agentes não respondem | DeepSeek API key faltando | Preencha `DEEPSEEK_API_KEY` |
| "No space left on device" | Disco cheio | `docker system prune -af` |
| FAISS index building lento | Primeira execução | Aguarde ~2min (download modelo BGE) |

### Comandos de Diagnóstico

```bash
# Logs do backend
docker logs ceara_queimadas_backend -f --tail 50

# Logs do frontend
docker logs ceara_queimadas_frontend -f --tail 50

# Teste rápido: saúde da API
curl http://localhost:8000/health

# Teste: listar endpoints disponíveis
curl http://localhost:8000/openapi.json | python3 -m json.tool | head -50
```
