# API e Interface Web

## Endpoints principais (dados reais)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | /api/v1/real/focos | Focos NASA FIRMS no Ceará (parâmetro dias 1-7) |
| GET | /api/v1/real/clima | Clima dos municípios |
| GET | /api/v1/real/focos/{id}/explicacao | Análise DeepSeek do foco |
| POST | /api/v1/real/focos/explicar-lote | Até 10 explicações |
| GET | /api/v1/real/status | Status NASA, Open-Meteo, Nominatim, DeepSeek |
| POST | /api/v1/pesquisa/chat | Chat RAG sobre a aplicação |
| GET | /api/v1/pesquisa/status | Status do índice FAISS |
| GET | /health | Health check |

## Páginas do frontend

| Rota | Página | Função |
|------|--------|--------|
| / | Dashboard | KPIs e visão executiva |
| /mapa-real | Mapa Real | Focos NASA FIRMS + explicação por clique |
| /mapa | Mapa | Camadas simuladas / completas |
| /alertas | Alertas | Listagem de alertas |
| /chat | Chat operacional | Agente ReAct (dados operacionais) |
| /guia | Guia da aplicação | Chat RAG FAISS — pesquisa e manual |
| /boletim | Boletim | Relatório técnico |

## Variáveis de ambiente do frontend

- `VITE_API_URL=/api/v1` em produção (nginx faz proxy)
- Em desenvolvimento, Vite proxy encaminha `/api` para localhost:8000

## Primeira carga do mapa real

A coleta FIRMS + geocoding pode levar 20-60 segundos na primeira requisição. O frontend usa timeout de 3 minutos para endpoints `/real/*`.
