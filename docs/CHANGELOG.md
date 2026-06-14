# Changelog — Gêmeo Digital Queimadas Ceará

Todas as mudanças notáveis neste projeto serão documentadas aqui.

O formato é baseado em [Keep a Changelog](https://keepachangelog.com/),
e o projeto segue [Semantic Versioning](https://semver.org/).

---

## [1.0.0] — 2026-06-13

### ✨ Destaques

- **Submissão completa** para Environmental Modelling & Software (Elsevier, Q1/A1)
- **Artigo científico**: 1028 linhas EN, ~533KB, compila com elsarticle 5p twocolumn
- **Modelo NeKo-PIGNN** híbrido validado com F1=0.9363
- **Pipeline GOES-19 + K-Means** validado com especificidade 100%

### 🚀 Funcionalidades

#### Detecção e Monitoramento
- Pipeline multi-satélite: GOES-16 (ABI-L2-FDCF), GOES-18, GOES-19
- Fusão GOES-16 + VIIRS (375m) — F1 subiu de 0.710 → 0.766
- Classificador 3-classes (NÃO / INCERTEZA / SIM) com precisão 100% na classe SIM
- K-Means não-supervisionado para detecção de focos GOES-16
- Validação cruzada com INPE BDQueimadas e NASA FIRMS

#### Agentes de IA
- Agente ReAct Diagnóstico (LangChain + DeepSeek)
- Agente Explicador NeKo-PIGNN com 6 ferramentas (DeepSeek + SHAP)
- Pipeline LangGraph completo (9 agentes)
- Agente Auditor de evidências (anti-falso-positivo)
- RAG com FAISS + fastembed para chat da pesquisa

#### Interface
- Dashboard React com KPIs, mapa MapLibre, timeline e ranking
- Chat IA com sugestões e evidências traceáveis
- Geração de boletim técnico

#### API
- Endpoints de dados reais (NASA FIRMS + Open-Meteo) — modo standalone
- Endpoints de inovação: Koopman, PI-GNN, NeKo-PIGNN, análise causal
- Endpoints de pesquisa (RAG)
- Swagger/ReDoc automáticos

#### Infraestrutura
- Docker Compose (PostgreSQL+PostGIS, Redis, Backend, Frontend)
- Deploy automatizado para AWS EC2 (Amazon Linux 2023)
- Nginx como proxy reverso

### 🧪 Experimentos e Validação

| Experimento | Resultado |
|-------------|-----------|
| Calibração Índice de Risco | F1=0.9363 (baseline 0.8325) |
| Pipeline GOES-19 + K-Means | Especificidade 100%, 95 focos deduped |
| Fusão GOES + VIIRS | Precisão 1.000, F1 0.766 |
| Pipeline sazonal (inverno) | Especificidade 100% |
| INOV-009 (Agente Explicador ReAct) | 7/7 testes de integração PASS |

### 📄 Artigo Científico
- 78 referências BibTeX (meta: 40+)
- CRediT padronizado PT/EN
- Figuras de qualidade: architecture, langraph, koopman, resultados, evolucao
- Cover letter com novelty statement
- Highlights formatados (5 bullet points)
- Checklist de submissão Elsevier

### 🐛 Correções
- Response truncated corrigido: timeout 180→600s + chunker.py
- Autores e afiliações corrigidos (Vladia Pinheiro: UNIFOR → IFCE)
- CRediT duplicado removido
- Tabela comparativa LaTeX (toprule sem espaço)
- CORS configurado para IP público AWS
- pyproj corrigido para GOES-19

---

## [0.9.0] — 2026-06-04

### ✨ Funcionalidades
- Pipeline K-Means + GOES-16 para detecção não-supervisionada
- Primeira versão do artigo Elsevier (seções 1-5)
- Coletor GOES-16 automático (cron a cada 3h)
- Integração INPE BDQueimadas + NASA FIRMS + GOES

### 🐛 Correções
- Workdir dos jobs Hermes atualizado (/Volumes/NAUBER)

---

## [0.8.0] — 2026-06-01

### ✨ Funcionalidades
- Modelo híbrido NeKo-PIGNN com acoplamento Koopman + GNN
- Neural Koopman Operator (PyTorch) — INOV-001
- Physics-Informed GNN com Rothermel Loss — INOV-002
- Endpoints FastAPI para modelos de inovação — INOV-004
- Dashboard de Inovação (React) — INOV-005

---

## [0.7.0] — 2026-05-25

### ✨ Funcionalidades
- Agentes LangChain + LangGraph completos
- Pipeline de orquestração (9 agentes)
- RAG com FAISS para chat da pesquisa
- Frontend React com mapa MapLibre

---

## [0.6.0] — 2026-05-15

### ✨ Funcionalidades
- Primeira versão funcional da API FastAPI
- Coleta INPE BDQueimadas e NASA FIRMS
- Classificador 3-classes (NÃO / INCERTEZA / SIM)

---

## [0.5.0] — 2026-05-01

### ✨ Funcionalidades
- Processamento GOES-16 (ABI-L2-FDCF)
- Detecção de focos por K-Means
- Validação com dados INPE

---

## [0.1.0] — 2026-04-15

### ✨ Funcionalidades
- Projeto inicial e estrutura do repositório
- Download e processamento GOES-16 via AWS S3


<!-- Links -->
[1.0.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v1.0.0
[0.9.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.9.0
[0.8.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.8.0
[0.7.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.7.0
[0.6.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.6.0
[0.5.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.5.0
[0.1.0]: https://github.com/naubergois/ceara-queimadas/releases/tag/v0.1.0
