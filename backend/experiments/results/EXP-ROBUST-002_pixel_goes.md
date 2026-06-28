# EXP-ROBUST-002 — GOES Pixel-Level INPE Evaluation

**Date:** 2026-06-28  
**Script:** `python -m src.pixel_inpe_eval`  
**Output:** `data/goes16_eval/metrics_pixel_inpe_2024-10-31.json`

## Configuration

- Date: 2024-10-31
- Hours UTC: 16, 17, 18
- Channels: 7, 13, 14
- Match radius: 15 km
- Contamination: 0.08
- ABI crop shape: 288×197 pixels

## Results (event-centered)

| Metric | Value |
|--------|-------|
| INPE focos (day) | 76 |
| TP pairs | 4 |
| FP clusters | 152 |
| FN focos | 72 |
| Precision | 0.026 |
| Recall | 0.053 |
| **F1** | **0.034** |

## Comparison with grid benchmark

| Method | F1 | Notes |
|--------|-----|-------|
| Pixel + cluster (this run) | 0.034 | Focal ↔ cluster matching |
| Digital twin 72×72 grid | 0.049 | Cell-level dilated truth |

## Reproduce

```bash
cd ceara-queimadas
.venv/bin/python -m src.pixel_inpe_eval \
  --inpe-csv data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv \
  --date 2024-10-31 --hours-utc 16,17,18 --channels 7,13,14 \
  --raw-dir data/goes16_raw --skip-download \
  --match-radius-km 15 --contamination 0.08 \
  --output-json data/goes16_eval/metrics_pixel_inpe_2024-10-31.json
```
