#!/usr/bin/env bash
# Reproduce INPE BDQueimadas CSVs for Ceará (used by EXP-ROBUST-003 and article).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${ROOT}/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON=python3
fi
echo "Downloading INPE Ceará focos 2024–2026..."
"$PYTHON" src/inpe_queimadas_download.py --start 2024 --end 2026
echo "Combined CSV: ${ROOT}/data/inpe_focos_ce/focos_ce_INPE_2024_2026.csv"
ls -lh "${ROOT}/data/inpe_focos_ce/anos/"*.csv 2>/dev/null || true
