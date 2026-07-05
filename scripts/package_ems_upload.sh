#!/usr/bin/env bash
# Zip LaTeX sources for Elsevier Editorial Manager upload.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
OUT="${ROOT}/submission/latex_source.zip"
rm -f "$OUT"
zip -rq "$OUT" \
  artigo-queimadas-gemeo-digital-en.tex \
  submission/refs-ems.bib \
  figures/*.tex \
  figures/*.png \
  figures/*.mmd \
  backend/experiments/results/tabela_*.tex \
  -x "*.aux" "*.log" "*.bak*"
echo "Created $OUT ($(du -h "$OUT" | cut -f1))"
