# EXP-ROBUST-001 — Bootstrap CI & Multi-Seed Regression

**Date:** 2026-06-28T14:02:34.908257+00:00
**Runtime:** 3.44s

## YES-class alert metrics (XGBoost 3-class, P≥0.30)

| Metric | Point | Bootstrap 95% CI |
|--------|-------|------------------|
| Precision | 100.0% | [0.0%, 100.0%] |
| Recall | 3.1% | [0.0%, 10.3%] |
| F1 | 0.061 | [0.000, 0.188] |
| TP / FP / FN | 1 / 0 / 31 | — |

## MLP regression (5 seeds, temporal split)

- RMSE: 0.1372 ± 0.0035 (95% CI [0.1334, 0.1429])
- R²: 0.800 (95% CI [0.783, 0.811])

## XGBoost regression (5 seeds, temporal split)

- RMSE: 0.1471 ± 0.0000
- R²: 0.770

## Paired significance tests

- Wilcoxon RMSE (MLP vs XGB): p=0.0625, Δmean=-0.0099
- McNemar 3-class (XGB vs persistence): p=0.1418
- McNemar YES alert: p=0.8714

## Reproduce
```bash
cd backend && python -m experiments.statistical_robustness
```

## Published v9 alert metrics (binomial bootstrap, TP/FP from TASK-083_FINAL)

| Metric | Point | 95% CI |
|--------|-------|--------|
| XGBoost YES precision | 82.1% | [67.9%, 96.4%] |
| NeKo YES precision | 91.7% | [75.0%, 100.0%] |
| Combined coverage | 88.0% | [84.6%, 91.2%] |
