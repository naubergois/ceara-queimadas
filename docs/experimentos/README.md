# Experimentos — índice e reprodução

Este diretório indexa os registos de experimentos do **Gêmeo Digital de Queimadas do Ceará**. Cada ficheiro MD descreve a proposta, protocolo e resultados de uma linha de avaliação integrada no artigo LaTeX via `figures/experimentos-artigo.tex`.

## Documentação de protocolo

| Ficheiro | Conteúdo |
|----------|----------|
| [../DOCUMENTACAO_PESQUISA_E_TESTES.md](../DOCUMENTACAO_PESQUISA_E_TESTES.md) | Template de registo, comandos de reprodução, artefactos |
| [../METODOLOGIA_NOVA_PROPOSTA.md](../METODOLOGIA_NOVA_PROPOSTA.md) | Linhas A–E: PEAK+PERSIST, consenso multi-vista, avaliação GOES↔INPE |
| [../EXPLICACAO_SISTEMA_DETECCAO.md](../EXPLICACAO_SISTEMA_DETECCAO.md) | Problema binário, solução em 3 classes, pipeline operacional |

## Resultados TASK-083 (predição municipal)

| Ficheiro | Versão | Resultado-chave |
|----------|--------|-----------------|
| [../../backend/experiments/results/TASK-083_FINAL.md](../../backend/experiments/results/TASK-083_FINAL.md) | v9 | **82% precisão alertas, 88% cobertura, 5 FP** |
| [../../backend/experiments/results/TASK-083_v8_tres_classes.md](../../backend/experiments/results/TASK-083_v8_tres_classes.md) | v8 | Formulação NO/INCERTEZA/SIM |
| [../../backend/experiments/results/TASK-083_v7_precisao_final.md](../../backend/experiments/results/TASK-083_v7_precisao_final.md) | v7 | Persistence prior → 47% |
| [../../backend/experiments/results/TASK-083_v5_final.md](../../backend/experiments/results/TASK-083_v5_final.md) | v5 | NeKo + weighted loss → 34% |
| [../../backend/experiments/results/TASK-083_v3_dados_reais.md](../../backend/experiments/results/TASK-083_v3_dados_reais.md) | v3 | MLP binário baseline → 21% |
| [../../backend/experiments/results/DETECCOES_REAIS.md](../../backend/experiments/results/DETECCOES_REAIS.md) | — | 377 focos, 97 dias, figuras de validação |

## Artefactos LaTeX e relatórios

| Ficheiro | Uso no artigo |
|----------|---------------|
| [../../artifacts/resultados-dados-reais.tex](../../artifacts/resultados-dados-reais.tex) | Secção completa de resultados (TASK-037) |
| [../../artifacts/TASK-037-relatorio.md](../../artifacts/TASK-037-relatorio.md) | Resumo executivo TASK-037 |
| [../../figures/experimentos-artigo.tex](../../figures/experimentos-artigo.tex) | Fragmento incluído em `artigo-queimadas-gemeo-digital*.tex` |
| [../../figures/tabela_real_data.tex](../../figures/tabela_real_data.tex) | Tabela comparativa em dados reais |

## Comandos rápidos

```bash
# Benchmark GOES-16 vs INPE (Linha B/E)
python -m src.unsupervised_fire_goes --method all \
  --inpe-csv data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv \
  --dates 2024-10-31 --hours-utc 16,17,18 \
  --channels 7,13,14 --truth-dilate 1 --calibrate-contamination

# Benchmark TASK-083 (predição 3 classes)
cd backend && python -m experiments.validate_real_data

# Testes automatizados
pytest tests/ -v
```

## Integração no artigo

A secção **Experimental Results** do manuscrito Elsevier inclui:

1. **Experimental Design and Protocol** — quatro tracks (A–D)
2. **Reference Datasets** — INPE 111k + subset TASK-083
3. **GOES-16 Benchmark** — Tabela de 5 métodos
4. **Three-Level Alert System** — métricas v8/v9
5. **NeKo-PIGNN validation** — regressão, detecção, ablação
6. **Operational performance** — 18 meses, agentes, RAG

*Última atualização: 2026-06-23*
