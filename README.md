# 🔥 Gêmeo Digital do Ceará — Queimadas

> Plataforma de monitoramento inteligente de queimadas no Estado do Ceará com IA agêntica, dados de satélite em tempo quase real e interface web interativa.

[![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![LangChain](https://img.shields.io/badge/LangChain-0.3-1C3C3C?logo=langchain)](https://langchain.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2-1C3C3C)](https://langchain-ai.github.io/langgraph)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+PostGIS-336791?logo=postgresql)](https://postgis.net)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.5-EE4C2C?logo=pytorch)](https://pytorch.org)
[![Koopman](https://img.shields.io/badge/Koopman-Neural-8B5CF6)](https://arxiv.org/abs/2305.18861)
[![GNN](https://img.shields.io/badge/PI--GNN-Physics--Informed-10B981)](https://arxiv.org/abs/2106.09494)
[![arXiv](https://img.shields.io/badge/arXiv-2604.05018-B31B1B)](https://arxiv.org/abs/2604.05018)

---

## 📋 Sumário

- [Visão Geral](#-visão-geral)
- [Arquitetura](#-arquitetura)
- [Fontes de Dados](#-fontes-de-dados)
- [Stack Tecnológica](#-stack-tecnológica)
- [Estrutura do Projeto](#-estrutura-do-projeto)
- [Pré-requisitos](#-pré-requisitos)
- [Instalação e Execução](#-instalação-e-execução)
- [API Reference](#-api-reference)
- [Agentes de IA](#-agentes-de-ia)
- [Pipeline LangGraph](#-pipeline-langgraph)
- [Interface React](#-interface-react)
- [Variáveis de Ambiente](#-variáveis-de-ambiente)
- [Contribuindo](#-contribuindo)

---

## 🌐 Visão Geral

O **Gêmeo Digital do Ceará para Queimadas** é uma plataforma operacional que detecta, monitora, valida, prioriza e alerta sobre queimadas no Estado do Ceará em tempo quase real.

O sistema funciona como um **gêmeo digital do território cearense**, permitindo acompanhar:

| Capacidade | Descrição |
|---|---|
| 🔥 Focos ativos | Detecção via INPE, NASA FIRMS e GOES-16 |
| 🌡️ Risco climático | Índice calculado com FUNCEME e INMET |
| 📡 GOES-16 | Persistência, FRP e evolução temporal dos focos |
| 🗺️ Cruzamento espacial | Municípios, UCs, áreas urbanas via PostGIS |
| 🤖 IA agêntica | Agentes ReAct com LangChain + LangGraph |
| 🚨 Alertas explicáveis | Com justificativa técnica e auditoria |
| 💬 Chat inteligente | Perguntas em linguagem natural |

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        FONTES DE DADOS                          │
│  INPE │ NASA FIRMS │ GOES-16 │ FUNCEME │ INMET │ MapBiomas      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────┐
              │   ETL / Coleta Periódica │
              │   (Celery + Redis)       │
              └────────────┬────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │  Validação com Pydantic  │
              └────────────┬────────────┘
                           │
                           ▼
         ┌─────────────────────────────────┐
         │   PostgreSQL + PostGIS           │
         │   (focos, eventos, clima, UCs)   │
         └────────────────┬────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │  LangGraph Orquestrador│
              └──────────┬────────────┘
                         │
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
  [Agente Geo]   [Agente GOES-16]  [Agente Clima]
        │                │                │
        └────────────────┼────────────────┘
                         │
                         ▼
            ┌────────────────────────┐
            │  Agente ReAct Diagnóstico│
            │  (LangChain + OpenAI)   │
            └────────────┬───────────┘
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
        [Alertas]            [Boletim Técnico]
              │                     │
              └──────────┬──────────┘
                         ▼
              ┌─────────────────────┐
              │   API FastAPI        │
              │   + Frontend React   │
              └─────────────────────┘
```

---

## 📡 Fontes de Dados

| Fonte | Uso | Frequência |
|---|---|---|
| **INPE BDQueimadas** | Focos oficiais no Brasil | A cada 15 min |
| **NASA FIRMS** (MODIS/VIIRS) | Validação cruzada | A cada 15 min |
| **GOES-16** (NOAA S3) | Detecção quase em tempo real, FRP, persistência | A cada 15 min |
| **MapBiomas Fogo** | Histórico de áreas queimadas e recorrência | Diário |
| **MapBiomas Uso e Cobertura** | Tipo de vegetação e vulnerabilidade | Mensal |
| **FUNCEME** | Chuva, seca, clima do Ceará | Horário |
| **INMET** | Temperatura, umidade, vento | Horário |
| **CPTEC/INPE** | Previsão meteorológica | Diário |
| **IPECE** | Camadas territoriais do Ceará | Estático |
| **IBGE** | Malhas municipais e limites | Estático |

---

## 🛠️ Stack Tecnológica

### Backend
| Tecnologia | Versão | Função |
|---|---|---|
| **Python** | 3.12 | Linguagem principal |
| **FastAPI** | 0.115 | API REST assíncrona |
| **LangChain** | 0.3 | Agentes especializados com ferramentas |
| **LangGraph** | 0.2 | Orquestração do pipeline de agentes |
| **Pydantic** | 2.10 | Validação e estruturação de dados |
| **SQLAlchemy** | 2.0 | ORM assíncrono |
| **PostgreSQL + PostGIS** | 16 + 3.4 | Banco geoespacial |
| **Celery + Redis** | 5.4 | Coleta periódica e filas |
| **boto3** | 1.35 | Acesso ao GOES-16 via AWS S3 |
| **netCDF4 + numpy** | — | Processamento de dados GOES-16 |

### Frontend
| Tecnologia | Versão | Função |
|---|---|---|
| **React** | 18 | Interface web |
| **TypeScript** | 5.7 | Tipagem estática |
| **Vite** | 6 | Build e dev server |
| **react-map-gl + MapLibre** | 7 + 4 | Mapa interativo |
| **deck.gl** | 9 | Visualizações geoespaciais avançadas |
| **Recharts** | 2.13 | Gráficos e timeline |
| **Zustand** | 5 | Gerenciamento de estado |
| **Tailwind CSS** | 3.4 | Estilização |

---

## 📁 Estrutura do Projeto

```
ceara-queimadas/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── react_agent.py        # Agente ReAct de diagnóstico (LangChain)
│   │   │   ├── auditor_agent.py      # Agente Auditor de evidências
│   │   │   └── langgraph_pipeline.py # Pipeline LangGraph completo
│   │   ├── api/
│   │   │   └── routes.py             # Endpoints FastAPI
│   │   ├── core/
│   │   │   ├── config.py             # Configurações (pydantic-settings)
│   │   │   ├── database.py           # SQLAlchemy async + PostGIS
│   │   │   └── orm_models.py         # Modelos ORM
│   │   ├── models/
│   │   │   └── schemas.py            # Schemas Pydantic (validação)
│   │   ├── services/
│   │   │   ├── inpe_service.py       # Coleta INPE BDQueimadas
│   │   │   ├── firms_service.py      # Coleta NASA FIRMS
│   │   │   ├── goes16_service.py     # Coleta e processamento GOES-16
│   │   │   ├── clima_service.py      # Coleta FUNCEME + INMET
│   │   │   └── geo_service.py        # Cruzamento espacial PostGIS
│   │   ├── tools/
│   │   │   └── queimada_tools.py     # Ferramentas LangChain
│   │   └── main.py                   # Ponto de entrada FastAPI
│   ├── migrations/                   # Alembic migrations
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── MapaQueimadas.tsx     # Mapa interativo (MapLibre)
│   │   │   ├── ChatAgente.tsx        # Chat com agente ReAct
│   │   │   ├── CardAlerta.tsx        # Card de alerta
│   │   │   ├── PainelRiscoMunicipal.tsx  # Ranking de risco
│   │   │   ├── TimelineEventos.tsx   # Evolução temporal
│   │   │   ├── DashboardOperacional.tsx  # KPIs executivos
│   │   │   └── CamadasControle.tsx   # Controle de camadas
│   │   ├── hooks/
│   │   │   └── useQueimadas.ts       # Hook de dados com polling
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx     # Visão executiva
│   │   │   ├── MapaPage.tsx          # Mapa completo
│   │   │   ├── AlertasPage.tsx       # Listagem de alertas
│   │   │   ├── ChatPage.tsx          # Interface de chat
│   │   │   └── BoletimPage.tsx       # Geração de boletim
│   │   ├── services/
│   │   │   └── api.ts                # Cliente HTTP (axios)
│   │   └── store/
│   │       └── useQueimadasStore.ts  # Estado global (Zustand)
│   ├── index.html
│   └── package.json
├── docker/
│   ├── docker-compose.yml
│   └── init-db.sql
└── README.md
```

---

## ✅ Pré-requisitos

- **Docker** 24+ e **Docker Compose** v2
- **Python** 3.12+ (para desenvolvimento local do backend)
- **Node.js** 20+ (para desenvolvimento local do frontend)
- **Chave de API OpenAI** (para os agentes LangChain)
- **Chave NASA FIRMS** (gratuita em [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/))

---

## 🚀 Instalação e Execução

### 1. Clone o repositório

```bash
git clone https://github.com/naubergois/ceara-queimadas.git
cd ceara-queimadas
```

### 2. Configure as variáveis de ambiente

```bash
cp backend/.env.example backend/.env
# Edite backend/.env com suas chaves de API
```

Variáveis obrigatórias:
```env
OPENAI_API_KEY=sk-...
NASA_FIRMS_API_KEY=sua-chave
```

### 3. Suba com Docker Compose

```bash
cd docker
docker compose up -d
```

Serviços disponíveis:
| Serviço | URL |
|---|---|
| Frontend React | http://localhost:5173 |
| API FastAPI | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 4. Desenvolvimento local (sem Docker)

**Backend:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

---

## 📡 API Reference

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/api/v1/focos/tempo-real` | Focos recentes (filtro por horas e fonte) |
| `GET` | `/api/v1/focos/municipio/{nome}` | Focos por município |
| `GET` | `/api/v1/risco/municipios` | Ranking de risco municipal |
| `GET` | `/api/v1/alertas/ativos` | Alertas ativos |
| `GET` | `/api/v1/goes16/eventos` | Eventos GOES-16 |
| `POST` | `/api/v1/agente/pergunta` | Chat com agente ReAct |
| `GET` | `/api/v1/relatorios/boletim` | Gerar boletim técnico |
| `GET` | `/api/v1/eventos/{id}` | Detalhe de evento |
| `GET` | `/api/v1/mapa/camadas` | Camadas disponíveis |
| `GET` | `/health` | Health check |

**Exemplo — pergunta ao agente:**
```bash
curl -X POST http://localhost:8000/api/v1/agente/pergunta \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quais municípios do Ceará estão com risco crítico hoje?"}'
```

**Resposta:**
```json
{
  "pergunta": "Quais municípios...",
  "resposta": "Com base nos dados consultados...",
  "evidencias": ["[buscar_focos_recentes]: ...", "[buscar_risco_municipal]: ..."],
  "fontes": ["buscar_focos_recentes", "buscar_risco_municipal"],
  "nivel_confianca": 0.85,
  "recomendacao_operacional": "Acionar equipes de monitoramento...",
  "ferramentas_usadas": ["buscar_focos_recentes", "buscar_risco_municipal"],
  "passos_raciocinio": ["Ação: buscar_focos_recentes | ..."]
}
```

---

## 🤖 Agentes de IA

### Agentes LangChain

| Agente | Responsabilidade |
|---|---|
| **Agente Coletor** | Consulta INPE, NASA FIRMS, GOES-16, FUNCEME e INMET |
| **Agente Geoespacial** | Cruza focos com municípios, UCs e uso do solo (PostGIS) |
| **Agente Climático** | Calcula risco usando chuva, vento, umidade e temperatura |
| **Agente GOES-16** | Analisa persistência, FRP, temperatura e evolução dos focos |
| **Agente Validador** | Verifica consistência dos dados com Pydantic |
| **Agente ReAct Diagnóstico** | Raciocina sobre causa, risco e prioridade (padrão ReAct) |
| **Agente de Alerta** | Gera mensagens para gestores e equipes operacionais |
| **Agente Relator** | Produz boletins técnicos e sumários executivos |
| **Agente Auditor** | Verifica se alertas têm evidências suficientes (anti-falso-positivo) |

### Ferramentas LangChain disponíveis

```python
buscar_focos_recentes       # Focos por município, janela de tempo e fonte
buscar_dados_climaticos     # Temperatura, umidade, vento, dias sem chuva
buscar_risco_municipal      # Índice de risco calculado por município
buscar_dados_goes16         # Leituras GOES-16 com FRP e persistência
buscar_historico_mapbiomas  # Histórico de queimadas por município
listar_municipios_criticos  # Ranking dos municípios mais críticos
```

### Padrão ReAct

O agente de diagnóstico segue o ciclo **Pensamento → Ação → Observação**:

```
Pergunta: "Há risco crítico de queimada hoje no Sertão Central?"

Pensamento: Preciso verificar focos recentes e dados climáticos
Ação: buscar_focos_recentes
Entrada: {"municipio": "Quixadá", "horas": 24}
Observação: {"total": 8, "focos": [...]}

Pensamento: Preciso verificar o clima
Ação: buscar_dados_climaticos
Entrada: {"municipio": "Quixadá"}
Observação: {"umidade_relativa": 28, "dias_sem_chuva": 15, ...}

Pensamento: Preciso confirmar com GOES-16
Ação: buscar_dados_goes16
Entrada: {"municipio": "Quixadá", "horas": 6}
Observação: {"total": 3, "leituras_goes16": [...]}

Pensamento: Tenho evidências suficientes
Resposta Final: Sim, risco CRÍTICO confirmado. 8 focos nas últimas 24h,
GOES-16 confirmou 3 pixels com fogo, umidade de 28% e 15 dias sem chuva.
Recomendação: Acionar Defesa Civil imediatamente.
```

---

## 🔄 Pipeline LangGraph

O grafo LangGraph orquestra o fluxo completo de análise:

```
START
  │
  ▼
coletar_dados          ← INPE + NASA FIRMS + GOES-16 + FUNCEME
  │
  ▼
validar_dados          ← Pydantic (rejeita registros inválidos)
  │
  ├──────────────────────────────┐
  ▼                              ▼                    ▼
agente_geoespacial    agente_goes16         agente_climatico
(PostGIS)             (FRP, persistência)   (seca, vento, umidade)
  │                              │                    │
  └──────────────────────────────┘────────────────────┘
                                 │
                                 ▼
                        fundir_evidencias
                                 │
                                 ▼
                        classificar_risco
                                 │
                                 ▼
                    agente_react_diagnostico  ← LangChain ReAct
                                 │
                                 ▼
                          gerar_alertas
                                 │
                                 ▼
                          gerar_boletim
                                 │
                                END
```

---

## 🖥️ Interface React

### Páginas

| Página | Rota | Descrição |
|---|---|---|
| **Dashboard** | `/` | KPIs, timeline, ranking de risco e alertas |
| **Mapa** | `/mapa` | Mapa interativo com focos e camadas |
| **Alertas** | `/alertas` | Listagem completa com filtros por nível |
| **Chat IA** | `/chat` | Interface conversacional com agente ReAct |
| **Boletim** | `/boletim` | Geração de relatório técnico |

### Componentes principais

| Componente | Função |
|---|---|
| `MapaQueimadas` | Mapa MapLibre com focos INPE, FIRMS, GOES-16 e heatmap |
| `ChatAgente` | Chat com sugestões, evidências e raciocínio do agente |
| `PainelRiscoMunicipal` | Ranking com barra de risco e justificativa |
| `TimelineEventos` | Gráfico de área por fonte e hora |
| `CardAlerta` | Card com nível, recomendação e confiança |
| `CamadasControle` | Toggle de camadas do mapa |
| `DashboardOperacional` | KPIs: focos, emergências, municípios críticos, GOES-16 |

### Perguntas suportadas no chat

```
Quais municípios do Ceará estão com maior risco hoje?
Existe algum foco próximo a unidade de conservação?
O GOES-16 confirmou crescimento do fogo nas últimas imagens?
Quais focos apareceram nas últimas 3 horas?
Gere um boletim para a Defesa Civil.
Explique por que este município está classificado como risco crítico.
Compare os focos do INPE com os do NASA FIRMS.
Mostre os eventos persistentes detectados pelo GOES-16.
```

---

## ⚙️ Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | ✅ | Chave OpenAI para os agentes LangChain |
| `NASA_FIRMS_API_KEY` | ✅ | Chave NASA FIRMS (gratuita) |
| `DATABASE_URL` | ✅ | URL PostgreSQL+PostGIS |
| `REDIS_URL` | ✅ | URL Redis |
| `OPENAI_MODEL` | — | Modelo OpenAI (padrão: `gpt-4o`) |
| `INPE_API_KEY` | — | Token INPE BDQueimadas |
| `FUNCEME_API_KEY` | — | Token FUNCEME |
| `INMET_TOKEN` | — | Token INMET |
| `MAPBIOMAS_TOKEN` | — | Token MapBiomas |
| `ALERTA_WEBHOOK_URL` | — | Webhook para notificações externas |
| `SMTP_HOST` | — | Servidor SMTP para alertas por e-mail |
| `DEBUG` | — | Modo debug (padrão: `false`) |

---

## 🗄️ Banco de Dados

Tabelas principais no PostgreSQL + PostGIS:

| Tabela | Conteúdo |
|---|---|
| `focos_queimada` | Focos detectados por fonte (INPE, FIRMS, GOES-16) |
| `eventos_consolidados` | Agrupamento de focos em eventos |
| `leituras_goes16` | Dados extraídos do GOES-16 |
| `municipios_ceara` | Malha municipal com geometria |
| `risco_municipal` | Índice de risco calculado por município |
| `dados_climaticos` | Chuva, vento, umidade e temperatura |
| `alertas` | Alertas gerados com rastreabilidade |
| `areas_sensiveis` | UCs, áreas urbanas, equipamentos, infraestrutura |
| `historico_mapbiomas` | Cicatrizes e recorrência de fogo |
| `logs_agentes` | Decisões e ferramentas chamadas pelos agentes |

---

## 🔍 Rastreabilidade e Auditoria

Cada alerta registra:
- Fonte dos dados e data/hora da coleta
- Agente responsável e ferramentas consultadas
- Evidências usadas na decisão
- Nível de confiança
- Justificativa em linguagem natural
- Flag de suspeita de falso positivo

O **Agente Auditor** verifica automaticamente:
- Se o alerta é justificável com as evidências disponíveis
- Se há divergência entre GOES-16, INPE e NASA FIRMS
- Se dados climáticos reforçam ou enfraquecem o risco

---

## 🤝 Contribuindo

1. Fork o repositório
2. Crie uma branch: `git checkout -b feature/minha-feature`
3. Commit: `git commit -m 'feat: adiciona minha feature'`
4. Push: `git push origin feature/minha-feature`
5. Abra um Pull Request

---

## 📄 Licença

MIT © 2025 — Desenvolvido para monitoramento público de queimadas no Estado do Ceará.

---

## 🙏 Agradecimentos

- [INPE BDQueimadas](https://queimadas.dgi.inpe.br) — dados oficiais de focos
- [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov) — MODIS e VIIRS
- [NOAA GOES-16](https://www.goes.noaa.gov) — imagens em tempo quase real
- [FUNCEME](https://www.funceme.br) — dados climáticos do Ceará
- [MapBiomas](https://mapbiomas.org) — histórico de uso e cobertura
- [LangChain](https://langchain.com) e [LangGraph](https://langchain-ai.github.io/langgraph) — framework de agentes

## 📚 Documentação Adicional

| Documento | Descrição |
|-----------|-----------|
| [Guia de Instalação](docs/GUIA_DE_INSTALACAO.md) | Instalação do zero (Docker, manual, AWS) |
| [Guia de Treinamento](docs/GUIA_TREINAMENTO.md) | Treinamento para operadores, analistas e devs |
| [Changelog](docs/CHANGELOG.md) | Histórico de versões e evolução |
| [Explicação do Sistema de Detecção](docs/EXPLICACAO_SISTEMA_DETECCAO.md) | Como funciona a detecção 3-classes |
| [Documentação de Pesquisa](docs/DOCUMENTACAO_PESQUISA_E_TESTES.md) | Testes e resultados experimentais |
| [Evolução da Pesquisa](docs/EVOLUCAO_PESQUISA.md) | Cronograma e evolução do projeto |
