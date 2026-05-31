# Deploy e Execução

## Desenvolvimento local

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-minimal.txt
python scripts/sync_deepseek_env.py   # copia DEEPSEEK_* de AIManager etc.
python scripts/build_faiss_index.py   # gera índice FAISS
uvicorn app.main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Docker Compose (modo completo)

```bash
cd docker && docker compose up -d
```

## EC2 Amazon Linux 2023

- User-data ou `deploy/finish-deploy.sh` instala nginx, Python 3.12, Node 20
- App em `/opt/unifor/app`
- Serviço systemd `unifor-backend`
- Nginx serve `frontend/dist` e proxy `/api/` → porta 8000

## Índice FAISS

- Gerado por `scripts/build_faiss_index.py`
- Armazenado em `data/faiss_pesquisa/`
- Na subida do backend, o índice é carregado automaticamente; se ausente, é construído em background

## Segurança

- Nunca commitar `.env` com chaves
- CORS inclui IP público da EC2 após deploy
- Security group: portas 80, 443, 8000, 22
