# Relatório de Calibração do Índice de Risco

## Data
2026-06-12T20:27:05Z

## Dataset
- Fonte: INPE BDQueimadas
- Registros INPE: 111,054
- Amostras positivas (com fogo): 19,249
- Amostras negativas (sem fogo): 11,362
- Período:  a 2026-05-09

## Baseline (pesos originais do artigo)
| Métrica | Valor |
|---------|-------|
| F1 | 0.8325 |
| Precisão | 1.0 |
| Recall | 0.7131 |
| Acurácia | 0.8196 |
| TP | 13727 |
| FP | 0 |
| TN | 11362 |
| FN | 5522 |

## Calibração Otimizada
| Métrica | Valor | Δ vs Baseline |
|---------|-------|---------------|
| F1 | 0.9363 | 0.1038 |
| Precisão | 0.9999 | -0.0001 |
| Recall | 0.8803 | 0.1672 |
| Acurácia | 0.9247 | |

## Pesos Otimizados
| Parâmetro | Baseline | Ótimo | Δ |
|-----------|----------|-------|---|
| `goes16_bonus` | 15.0 | 15.0 | +0.0 |
| `limiar_alto` | 50.0 | 45 | -5.0 |
| `limiar_critico` | 75.0 | 70 | -5.0 |
| `limiar_medio` | 25.0 | 20 | -5.0 |
| `max_clima_seca` | 30.0 | 20.0 | -10.0 |
| `max_clima_vento` | 20.0 | 20.0 | +0.0 |
| `max_focos` | 40.0 | 50.0 | +10.0 |
| `max_frp` | 10.0 | 10.0 | +0.0 |
| `w_clima_seca` | 1.5 | 2.5 | +1.0 |
| `w_clima_umidade` | 0.4 | 0.6 | +0.2 |
| `w_clima_vento` | 1.5 | 1.5 | +0.0 |
| `w_focos` | 8.0 | 12.0 | +4.0 |
| `w_frp` | 0.01 | 0.01 | +0.0 |

## Interpretação
- A calibração baseia-se em dados históricos INPE (2024-2026) para o estado do Ceará.
- O índice de risco é calculado conforme Eqs. 1-2 do artigo (artigo-queimadas-gemeo-digital-en.tex, §Risk Classifier).
- A otimização busca maximizar F1 (equilíbrio precisão-recall), priorizando a detecção correta de eventos com queimada.
- **Limitação:** Os dados INPE não incluem medições diretas de umidade relativa e vento para cada registro. Foram usados proxies (dias_sem_chuva para umidade, risco_fogo para vento).
- **Limitação:** Sem dados GOES-16 históricos completos, o bônus GOES-16 não pôde ser calibrado diretamente.
