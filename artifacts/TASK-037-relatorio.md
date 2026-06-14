## TASK-037 — Artigo Elsevier: Resultados — Dados Reais e Validação
## Executor: time-pesqusia-technical-writer-2
## Data: 2026-06-14
## Status: Concluído

## Fontes de Dados Utilizadas
- INPE BDQueimadas Ceará 2024–2026: 111.054 registros
- NASA FIRMS (VIIRS + MODIS): 38.400+ detecções
- GOES-16 ABI CMIPF validação: 5 métodos × 3h
- DeepSeek Chat API: 100 perguntas de teste
- FAISS RAG: 30 perguntas, 42 documentos

## Artefatos Gerados (salvos apenas em workspace/artifacts)
- `resultados-dados-reais.tex` — Seção completa de Resultados (7 subseções, 7 tabelas)
- `TASK-037-relatorio.md` — Este relatório

## Resumo dos Resultados
1. INPE: 111.054 focos, 184 municípios, 85% na estação seca
2. GOES vs INPE: F1 máximo 0,049 (Digital Twin multibanda)
3. FIRMS: VIIRS SNPP 48%, NOAA-20 36%, MODIS 16%
4. Agentes: ReAct 97% sucesso, fallback 100% cobertura
5. RAG: recall@5 91%, 89% respostas completas
6. NeKo-PIGNN: F1=0,9140 (completo) vs 0,8200 (Koopman-only)
7. Operacional: 18 meses, >99% disponibilidade, $20/mês USD
