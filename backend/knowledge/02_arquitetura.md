# Arquitetura do Sistema

## Camadas

1. **Fontes externas**: NASA FIRMS (CSV público), Open-Meteo, Nominatim, INPE, GOES-16, MapBiomas (planejado)
2. **Backend FastAPI** (Python 3.12): APIs REST, cache em memória, agentes LangChain
3. **Frontend React** (Vite + TypeScript): mapa, dashboard, chat, boletim
4. **Proxy Nginx** (produção EC2): serve frontend estático e encaminha `/api/` ao uvicorn

## Modos de operação

### Modo standalone (padrão em produção EC2)

- Não exige PostgreSQL nem Redis
- Endpoints em `/api/v1/real/*` consultam APIs externas diretamente
- Cache de focos em memória (TTL 5 minutos)
- Geocodificação Nominatim em amostra + background

### Modo completo (com Docker Compose)

- PostgreSQL + PostGIS para persistência geoespacial
- Redis + Celery para coleta periódica
- Endpoints adicionais em `/api/v1/focos/tempo-real`, alertas, GOES-16 persistido

## Pipeline LangGraph (modo completo)

Fluxo: coletar_dados → validar_dados → agentes paralelos (geo, GOES-16, clima) → fundir_evidencias → classificar_risco → agente_react_diagnostico → gerar_alertas → gerar_boletim

## LLM

O sistema usa **DeepSeek** (`deepseek-chat`) via API compatível com OpenAI. A chave pode vir do `.env` local ou de projetos irmãos (AIManager, GerenciaTreinamentos) através de `secrets_fallback.py`.

## RAG — Chat da pesquisa

Documentos em `backend/knowledge/` são fragmentados e indexados em **FAISS**. O chat `/api/v1/pesquisa/chat` recupera trechos relevantes e o DeepSeek responde citando o contexto da aplicação.
