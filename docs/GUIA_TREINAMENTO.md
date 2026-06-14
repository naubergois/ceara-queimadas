# 🎓 Guia de Treinamento — Gêmeo Digital Queimadas Ceará

> Material de treinamento para operadores, desenvolvedores e tomadores de decisão.

---

## Público-Alvo

| Perfil | O que aprenderá | Tempo estimado |
|--------|----------------|----------------|
| **Operador** | Usar o dashboard, interpretar alertas, acionar resposta | 30 min |
| **Analista** | Consultar dados históricos, configurar parâmetros de risco | 1 h |
| **Desenvolvedor** | Modificar agentes, expor novos endpoints, adicionar fontes | 2 h |
| **Gestor** | Visão executiva, relatórios, tomada de decisão baseada em dados | 20 min |

---

## Módulo 1 — Visão Geral do Sistema

### 1.1 O que é o Gêmeo Digital?

O **Gêmeo Digital do Ceará para Queimadas** é uma plataforma que:

1. **Coleta** dados de satélite (GOES-16, VIIRS, MODIS) e clima (FUNCEME, INMET, Open-Meteo)
2. **Processa** com agentes de IA (LangChain + LangGraph) para detectar, validar e priorizar focos
3. **Alerta** gestores e equipes operacionais com justificativa técnica e nível de confiança
4. **Prevê** risco futuro usando modelos híbridos Neural Koopman + Physics-Informed GNN

### 1.2 Arquitetura em Camadas

```
Fontes Externas      →  Coleta            →  Inteligência     →  Interface
INPE / NASA FIRMS       ETL Periódica         Agentes ReAct        React + MapLibre
GOES-16 / GOES-19       Validação Pydantic    LangGraph Pipeline   Dashboard
FUNCEME / INMET         Cache Redis           RAG + FAISS          Chat IA
                       PostgreSQL+PostGIS    NeKo-PIGNN            Boletins
```

### 1.3 Fluxo de Decisão

```
Dado bruto (satélite)
    │
    ▼
Classificador 3-classes: NÃO / INCERTEZA / SIM
    │
    ├─ NÃO → Sem ação
    ├─ INCERTEZA → Monitorar GOES-16 (verificar em 6h)
    └─ SIM → 🚨 Alerta com justificativa técnica
        │
        ▼
    Agente ReAct confirma evidências
        │
        ▼
    Agente Auditor verifica falso-positivo
        │
        ▼
    Alerta final → Dashboard + Webhook + Email
```

---

## Módulo 2 — Operador: Usando o Dashboard

### 2.1 Acessando

```
URL: http://SEU_IP (ou http://localhost:5173 em desenvolvimento)
```

### 2.2 Páginas Principais

| Página | Rota | O que mostra |
|--------|------|-------------|
| **Dashboard** | `/` | KPIs: focos ativos, municípios críticos, últimas detecções GOES-16 |
| **Mapa** | `/mapa` | Mapa interativo com focos INPE, FIRMS, GOES-16, heatmap |
| **Alertas** | `/alertas` | Lista de alertas ativos com nível, fonte, confiança |
| **Chat IA** | `/chat` | Pergunte em linguagem natural sobre focos e riscos |
| **Boletim** | `/boletim` | Gere relatório técnico formatado |

### 2.3 Interpretando Alertas

Cada alerta contém:

```
🔥 Nível: CRÍTICO | Município: Quixadá | Confiança: 92%
📡 Fontes: INPE (8 focos), GOES-16 (3 pixels), VIIRS (1 hotspot)
🌡️ Clima: 38°C, umid. 28%, vento 25km/h, 15 dias sem chuva
💬 Justificativa: Focos persistentes há 3 dias, condições extremas
🎯 Recomendação: Acionar Defesa Civil imediatamente
🕵️ Auditoria: Evidências OK — sem suspeita de falso positivo
```

### 2.4 Perguntas que o Chat IA Responde

```
✅ "Quais municípios estão com risco crítico hoje?"
✅ "Mostre focos nas últimas 3 horas"
✅ "O GOES-16 confirmou crescimento do fogo?"
✅ "Compare INPE com NASA FIRMS"
✅ "Explique por que este município está em risco crítico"
✅ "Há foco próximo a unidade de conservação?"
✅ "Gere boletim para a Defesa Civil"
```

---

## Módulo 3 — Analista: Configurando Parâmetros

### 3.1 Limiares de Risco

Configurados em `backend/.env`:

```env
RISCO_CRITICO_THRESHOLD=75.0    # ≥75 → Alerta vermelho
RISCO_ALTO_THRESHOLD=50.0       # ≥50 → Alerta laranja
RISCO_MODERADO_THRESHOLD=25.0   # ≥25 → Alerta amarelo
```

### 3.2 Frequência de Coleta

```env
COLETA_INTERVALO_MINUTOS=15     # Coleta a cada 15 min
```

### 3.3 Métricas de Avaliação

O modelo é avaliado com:

| Métrica | Descrição | Alvo |
|---------|-----------|------|
| **F1-score** | Média harmônica precisão-recall | > 0.85 |
| **Precisão** | Acertos / total alertas SIM | > 0.90 |
| **Recall (Cobertura)** | Focos detectados / focos reais | > 0.80 |
| **IoU** | Interseção sobre união (mapeamento) | > 0.70 |
| **RMSE** | Erro quadrático médio de intensidade | < 0.15 |
| **Skill Score** | Ganho sobre baseline climatológico | > 0.30 |

---

## Módulo 4 — Desenvolvedor: API e Agentes

### 4.1 Endpoints da API

#### Dados Reais (modo standalone — sem banco)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/v1/focos/tempo-real` | Focos FIRMS recentes |
| `GET` | `/api/v1/focos/municipio/{nome}` | Focos por município |
| `GET` | `/api/v1/risco/municipios` | Ranking de risco municipal |
| `GET` | `/api/v1/alertas/ativos` | Alertas ativos |
| `POST` | `/api/v1/agente/pergunta` | Chat com agente ReAct |
| `GET` | `/api/v1/relatorios/boletim` | Boletim técnico |
| `GET` | `/health` | Health check |

#### Inovação (NeKo-PIGNN / Koopman)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/v1/prever-koopman` | Previsão com Operador de Koopman |
| `POST` | `/api/v1/prever-pignn` | Previsão com PI-GNN |
| `POST` | `/api/v1/prever-neko-pignn` | Previsão com modelo híbrido |
| `GET` | `/api/v1/modos-coerentes` | Modos coerentes de Koopman |
| `POST` | `/api/v1/analise-causal` | Análise causal ("e se?") |
| `GET` | `/api/v1/comparar-baseline` | Comparação com baselines |
| `GET` | `/api/v1/status-modelos` | Status dos modelos carregados |

#### Chat da Pesquisa (RAG)

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `POST` | `/api/v1/pesquisa/pergunta` | Pergunta sobre pesquisa (RAG) |
| `GET` | `/api/v1/pesquisa/status` | Status do índice FAISS |

### 4.2 Exemplo: Consultar Focos

```bash
curl "http://localhost:8000/api/v1/focos/tempo-real?horas=6&fonte=VIIRS"
```

### 4.3 Exemplo: Perguntar ao Agente

```bash
curl -X POST http://localhost:8000/api/v1/agente/pergunta \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Quais municípios do Ceará estão com risco crítico hoje?"}'
```

Resposta:
```json
{
  "resposta": "Com base nos dados...",
  "evidencias": ["[buscar_focos_recentes]: ..."],
  "nivel_confianca": 0.85,
  "recomendacao_operacional": "..."
}
```

### 4.4 Estrutura de Agentes

| Arquivo | Agente | Responsabilidade |
|---------|--------|-----------------|
| `agents/react_agent.py` | ReAct Diagnóstico | Raciocínio principal |
| `agents/auditor_agent.py` | Auditor | Verifica falsos positivos |
| `agents/langgraph_pipeline.py` | Orquestrador | Pipeline LangGraph |
| `agents/neko_explicador_agent.py` | Explicador NeKo | Explica previsões do modelo híbrido |
| `agents/explicador_agent.py` | Explicador Geral | Explicações em linguagem natural |
| `agents/llm_factory.py` | Fábrica de LLM | Cria clientes DeepSeek/OpenAI |

### 4.5 Ferramentas dos Agentes

```python
buscar_focos_recentes       # Focos por município, janela, fonte
buscar_dados_climaticos     # Temperatura, umidade, vento
buscar_risco_municipal      # Índice de risco municipal
buscar_dados_goes16         # FRP, persistência GOES-16
buscar_historico_mapbiomas  # Cicatrizes de fogo
listar_municipios_criticos  # Ranking de risco
```

### 4.6 Adicionar uma Nova Fonte de Dados

1. Crie um serviço em `backend/app/services/` (ex: `nova_fonte_service.py`)
2. Adicione uma ferramenta em `backend/app/tools/queimada_tools.py`
3. Registre a ferramenta no agente em `backend/app/agents/react_agent.py`
4. Crie um endpoint em `backend/app/api/` para expor os dados
5. Adicione as variáveis de ambiente em `backend/app/core/config.py`
6. Atualize `.env.example`

---

## Módulo 5 — Modelos de Inovação (NeKo-PIGNN)

### 5.1 Visão Geral

O sistema conta com três modelos de inovação:

| Modelo | Arquivo | Descrição |
|--------|---------|-----------|
| **Neural Koopman Operator** | `models/inovacao/koopman_operator.py` | Autoencoder para espaço latente linear |
| **Physics-Informed GNN** | `models/inovacao/pignn.py` | GNN com perda física de Rothermel |
| **NeKo-PIGNN (Híbrido)** | `models/inovacao/neko_pignn.py` | Koopman + PI-GNN acoplados |

### 5.2 Arquitetura NeKo-PIGNN

```
Dados (VIIRS/MODIS)
    │
    ▼
[Autoencoder] → Espaço Latente (d=64)
    │
    ├──→ Matriz K (Koopman) → z_{t+1} = K·z_t
    │
    ├──→ PI-GNN (Message Passing, L=3)
    │       └── Perda Física: Rothermel Loss
    │
    └──→ Correção: z_{t+1}^{corrigido} = f(z_{t+1}^{Koopman}, z_{t+1}^{GNN})
    │
    ▼
Previsão de Risco (12h horizonte)
```

### 5.3 Treinamento

```bash
# Treinar NeKo-PIGNN com dados reais
python scripts/treinar_neko_pignn_real.py

# Validar modelos
python backend/experiments/validate_models_v2.py
```

### 5.4 Avaliação do Modelo Híbrido

| Métrica | Koopman | PI-GNN | NeKo-PIGNN |
|---------|---------|--------|------------|
| RMSE (12h) | 0.142 | 0.128 | **0.103** |
| F1-score | 0.821 | 0.854 | **0.936** |
| Skill Score | 0.245 | 0.289 | **0.374** |

---

## Módulo 6 — FAQ para Treinamento

### O que fazer se o dashboard não carregar?

1. Verifique se o backend está rodando: `curl http://localhost:8000/health`
2. Verifique se o frontend foi buildado: `ls frontend/dist/`
3. Verifique logs: `docker logs ceara_queimadas_backend -f --tail 50`

### Como testar um alerta falso?

O sistema tem **Agente Auditor** que verifica automaticamente. Para testar:
- Consulte focos antigos que não existem mais: o auditor detecta divergência
- Simule dados climáticos contraditórios: o modelo rebaixa a confiança

### Qual a diferença entre INPE e NASA FIRMS?

| Fonte | Satélite | Resolução | Latência |
|-------|----------|-----------|----------|
| **INPE BDQueimadas** | AQUA, TERRA, NPP, NOAA20 | 375m–1km | ~15 min |
| **NASA FIRMS** | MODIS, VIIRS S-NPP, VIIRS NOAA-20 | 375m–1km | ~15 min |
| **GOES-16** | ABI (geoestacionário) | 2km | ~5 min |

O sistema cruza as três fontes para validação cruzada.

### Como interpretar o heatmap do mapa?

- **Vermelho escuro**: Alta densidade de focos confirmados por múltiplas fontes
- **Laranja**: Focos de uma fonte apenas, sem confirmação cruzada
- **Amarelo**: Risco projetado (sem foco ativo, mas condições propícias)

---

## Referências

- [README Principal](../README.md)
- [Guia de Instalação](GUIA_DE_INSTALACAO.md)
- [Explicação do Sistema de Detecção](EXPLICACAO_SISTEMA_DETECCAO.md)
- [Documentação de Pesquisa e Testes](DOCUMENTACAO_PESQUISA_E_TESTES.md)
- [Evolução da Pesquisa](EVOLUCAO_PESQUISA.md)
