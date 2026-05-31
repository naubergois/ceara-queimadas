# Agentes de Inteligência Artificial

## DeepSeek como LLM principal

- Modelo de chat: `deepseek-chat`
- Base URL: `https://api.deepseek.com`
- Factory: `app/agents/llm_factory.py`

## Agente explicador de focos (dados reais)

- Endpoint: `GET /api/v1/real/focos/{id}/explicacao`
- Busca clima Open-Meteo para o foco
- Gera explicação em português via DeepSeek (chamada direta, não ReAct)
- Fallback por regras se DeepSeek falhar

## Agente ReAct de diagnóstico

- Endpoint: `POST /api/v1/agente/pergunta` (requer banco em alguns deploys)
- Ferramentas: buscar_focos_recentes, buscar_dados_climaticos, buscar_risco_municipal, buscar_dados_goes16, etc.
- Padrão Pensamento → Ação → Observação

## Agente auditor

- Valida se alertas têm evidências suficientes
- Reduz falsos positivos

## Pipeline LangGraph

- Orquestra coleta, validação Pydantic, agentes paralelos e geração de boletim
- Arquivo: `langgraph_pipeline.py`

## Chat da pesquisa (RAG + FAISS)

- **Objetivo**: explicar metodologia, arquitetura e uso da aplicação
- **Não consulta focos ao vivo** — usa base documental em `backend/knowledge/`
- Embeddings: fastembed (`BAAI/bge-small-en-v1.5`) para o índice FAISS
- Geração das respostas: DeepSeek (`deepseek-chat`)
- Índice: `backend/data/faiss_pesquisa/`
